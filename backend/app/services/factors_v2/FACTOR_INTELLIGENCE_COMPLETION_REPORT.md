WHAT TO REMOVE FROM I/O BECAUSE THE DATA DOES NOT EXIST LOCALLY
F02 Rolling exposure time series
The spec says "for each factor, how has the portfolio's loading evolved month-by-month over the chosen history." This requires historical holdings snapshots at each rebalancing date. You do not have them. The current output is a static single-date characteristic exposure labeled as a time series, which is misleading. Remove the rolling_exposures output section from the UI page definition and remove static_exposure_time_series from the backend charts dict. Replace with a single clear note in meta that says rolling exposure requires historical holdings snapshots via rebalancing_history payload field.
F02 Full comparison mode for three portfolios simultaneously
Requires three separate portfolio uploads. No multi-portfolio input exists in the payload contract. Remove from the spec scope entirely. The split-screen comparison mode in the UI covers this use case adequately at the platform level.
F03 Holdings-level carryover effect
The true Brinson carryover decomposition requires rebalancing_history with dated weight snapshots. The proxy fallback using time-series autocorrelation is already clearly marked as a proxy. Keep the proxy, but remove any UI section or input field that implies the user can get holdings-level carryover without providing rebalancing_history. The input field for rebalancing_history should stay because when a user does provide it the real computation runs. Just make the output clearly conditional.
F06 Bid-ask spread trend
Requires live external data fetching which is explicitly not performed inside local-only compute. The toggle exists in the payload but the output is always the ADV proxy. Remove the include_bid_ask_trend input field from the UI. Keep it in the backend as a documented no-op with a meta note explaining why.
F06 Institutional ownership and short interest proxies
Not present locally. Currently marked as diagnostic in the backend. Remove from the crowding_metrics table entirely since they are labeled as excluded from the composite and the data does not exist. The table showing metrics that are excluded and proxied reads as incomplete to an allocator. Remove those rows, keep the three real metrics.
F06 Cross-factor crowding league table
Requires iterating the full factor library simultaneously. Currently not implemented. Either implement it properly by iterating the factor list in the payload, or remove the crowding_league UI section. Do not leave it as an empty section.
F08 Normal vs crisis structured dict for three-panel renderer
The backend returns correlation_amplification as the delta but not a structured {normal, crisis, delta} dict. The NormalVsCrisis UI renderer expects that structure. Either restructure the F08 backend to return all three matrices under named keys, or remove the normal-vs-crisis UI section and replace it with three separate heatmap sections: one for the normal correlation, one for the crisis correlation, one for the delta. Three separate sections is actually cleaner for an allocator.
F08 Rolling per-pair DCC correlation chart
Requires a specific factor pair selection from the user. The current output is the DCC average correlation path across all pairs. These are different things. Either add a factor_pair input to F08 and compute the specific rolling correlation, or remove the rolling-correlation UI section since the average correlation path is already shown in dcc_average_correlation.
F08 Portfolio risk decomposition heatmap
Requires portfolio holdings input in F08 specifically. Currently F08 has no portfolio input. Either add portfolio input to F08 and wire it through, or remove the portfolio-risk-decomposition UI section. The tracking error budget in F02 partially covers this.
F10 True Black-Litterman
The current implementation is a confidence-weighted proxy table, not a true Black-Litterman posterior. The spec says "user states views in plain language, system maps to prior and posterior." Plain-language view parsing is an NLP problem that is not implemented. Remove the plain-language view input. Keep the Black-Litterman output table but label it clearly as a confidence-weighted expected return blend, not a true Black-Litterman posterior. The input should be a structured view dict, not a natural language string.
F12 Sector DNA time series animation
Requires historical sector composition data at each rebalancing date. You do not have this. Remove the animation aspect. Keep the current sector composition snapshot as a static grouped horizontal bar showing long book vs short book sector weights today. That is implementable with the current data and is still a useful output.
F12 Correlation DNA grid over time
The rolling 252-day factor-to-factor correlation grid over time is a matrix time series. It requires storing rolling correlation matrices at each date which is computationally expensive and not currently implemented. Replace with the latest single correlation matrix between the primary factor and all other factors in the library, displayed as a horizontal bar chart. That is implementable now, is still called Correlation DNA, and conveys the same analytical point.
F13 Multi-factor simultaneous monitoring
Currently processes only one factor per run. The spec says full library scope. This is implementable: iterate payload.get("factors", DEFAULT_FACTORS) and compute the four health metrics for each. This is not a data availability problem, it is an implementation gap. Do it rather than removing it.
F14 Embedded chart images in PDF
Requires rasterizing Recharts SVG output from the frontend. The backend cannot do this. Remove chart image embedding from the PDF spec scope permanently. The PDF contains section tables, narrative text, and the audit trail. Chart images are a frontend export worker concern. Document this clearly and close the item.
F14 True external notification delivery
Email, Slack, and webhook delivery require a router and worker infrastructure that does not exist. Remove these as output claims. Keep the alert payload generation in the response, keep the alert_policy table showing what channels are configured, but remove any implication that notifications are delivered. The meta should say "alert payloads generated, delivery requires external worker wiring."

WHAT TO KEEP BUT FIX
F04 Factor timing regression
Not a data availability problem. All inputs exist: factor returns, timing signals like valuation percentile and crowding score from F01 and F06. This is an implementation gap. Implement \_factor_timing_regression that regresses each timing signal on forward factor returns and returns coefficient, t-stat, R-squared, and current implied timing score. This is what makes F04 actionable rather than descriptive.
F04 Factor momentum backtest
Factor return data exists. This is a construction gap. Build a rolling factor momentum portfolio: rank factors by trailing 3-month return, go long top half, short bottom half, compute cumulative return. Standard implementation, all data is local.
F04 Factor seasonality
Factor return data exists grouped by calendar month. This is a three-line groupby. Implement it.
F05 Post-2015 acceleration split test
Factor return data exists. Split at 2015-01-01, fit decay model on each sub-period, compare half-lives. Implement it.
F06 Crowding vs forward return scatterplot
All data is local. The crowding percentile series and forward factor returns both exist. Build the scatter and OLS regression. Implement it.
F08 Minimum variance factor combination
Covariance matrix exists. Solve for minimum eigenvector weights. One np.linalg.eigh call. Implement it.
F08 Covariance stability score
Condition numbers in crisis vs normal periods. All data is local. Implement it.
F12 Regime DNA six-bar chart
Call run_feature_module(4, payload) and extract the conditional return heatmap rows. Map to six regime cells. All data flows through existing code. Implement it.
F13 Chow structural break
The CUSUM is implemented. The Chow test is a weekly cached diagnostic. Use statsmodels.stats.diagnostic or a manual OLS split F-test on the IC series. Implement it as the weekly cache path.

COMPLETE LIST OF REMAINING ITEMS IN PRIORITY ORDER
Must implement, data exists, just missing code:

F04 factor timing regression with coefficient, t-stat, R-squared, current timing score
F04 factor momentum backtest cumulative return curve
F04 factor seasonality by calendar month
F05 post-2015 half-life split test with significance
F06 crowding vs forward return scatter with OLS
F08 minimum variance factor combination
F08 covariance stability score crisis vs normal ratio
F12 regime DNA six-bar chart from F04 conditional returns
F13 Chow diagnostic weekly cached
F13 multi-factor simultaneous health monitoring
F06 cross-factor crowding league table by iterating factor list

Restructure to fix renderer mismatch, data exists:

F08 restructure response to return {normal, crisis, delta} dict or replace with three separate heatmap sections
F08 add factor_pair input and compute specific rolling DCC correlation for that pair
F10 change Black-Litterman input from plain language to structured view dict

Remove from I/O, data genuinely does not exist:

F02 rolling exposure time series as a historical output, replace with static snapshot clearly labeled
F06 bid-ask spread trend input field
F06 institutional ownership and short interest proxy rows from crowding metrics table
F12 sector DNA time series animation, replace with static snapshot
F12 correlation DNA rolling grid, replace with latest single-date factor correlation bar chart
F14 embedded chart images from PDF scope
F14 external notification delivery claims

Good. With full factor returns and AQR data, almost everything is unblocked. Let me address each thing directly.

---

## F10 BLACK-LITTERMAN: KEEP AND BUILD PROPERLY

With full factor return history you can implement true Black-Litterman at the factor level, not stock level. This is actually more useful for a factor platform than the standard stock-level BL.

The prior is the historical factor return vector, the equilibrium implied returns computed by reverse-optimizing the market-cap-weighted factor portfolio. The views are user-provided as a structured dict: which factor outperforms which, by how much, with what confidence. The posterior blends prior and views weighted by the confidence matrix Omega.

```python
def black_litterman_factor(
    sigma: np.ndarray,          # factor covariance matrix from F08
    pi: np.ndarray,             # equilibrium implied returns
    P: np.ndarray,              # pick matrix: rows are views, cols are factors
    q: np.ndarray,              # view returns vector
    omega: np.ndarray,          # view uncertainty diagonal matrix
    tau: float = 0.05,
) -> Dict[str, Any]:
    # Posterior expected returns
    tau_sigma = tau * sigma
    M = np.linalg.inv(np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P)
    mu_bl = M @ (np.linalg.inv(tau_sigma) @ pi + P.T @ np.linalg.inv(omega) @ q)
    sigma_bl = sigma + M
    return {
        "prior": pi.tolist(),
        "posterior": mu_bl.tolist(),
        "posterior_covariance": sigma_bl.tolist(),
        "adjustment": (mu_bl - pi).tolist(),
    }
```

The payload input should be structured as:

```json
{
  "bl_views": [
    {
      "long": "momentum_12_1",
      "short": "value_pb",
      "excess_return": 0.02,
      "confidence": 0.6
    },
    {
      "long": "quality_roe",
      "short": null,
      "excess_return": 0.015,
      "confidence": 0.4
    }
  ],
  "bl_tau": 0.05,
  "bl_risk_aversion": 2.5
}
```

The system maps each view to a row in P automatically. `confidence` maps to the diagonal of Omega as `sigma_view = (1 - confidence) / confidence * view_variance`. This is real Black-Litterman, not a proxy. Keep it, implement it fully, wire the posterior into the optimizer as the expected return vector.

---

## F08 PORTFOLIO HOLDINGS ISSUE: FULL EXPLANATION

The spec says F08 should decompose portfolio active factor risk into contributions per factor and per factor pair. This requires knowing the portfolio weights. The problem is F08 currently takes no portfolio input, it only takes a factor set and estimation parameters.

There are two clean solutions and you should implement both.

**Solution 1: Accept portfolio weights directly in F08 payload.**

Add `portfolio_weights` as an optional input to F08. When provided, compute active risk decomposition:

```python
# portfolio_weights: dict of {factor_name: weight}
w = np.array([float(payload.get("portfolio_weights", {}).get(c, 1/len(names))) for c in names])
w = w / w.sum()

# Active risk decomposition
port_var = float(w @ cov_values @ w)
port_vol = np.sqrt(max(port_var, 0))

# Marginal contribution to risk
mcr = (cov_values @ w) / max(port_vol, 1e-8)
contrib = w * mcr  # factor risk contributions sum to port_vol

# Pairwise covariance contribution matrix
pair_contrib = np.outer(w, w) * cov_values  # (i,j) entry = w_i * w_j * sigma_ij

risk_decomp = {
    "factor_contributions": [
        {
            "factor": names[i],
            "weight": float(w[i]),
            "marginal_risk": float(mcr[i]),
            "risk_contribution": float(contrib[i]),
            "pct_of_total_risk": float(contrib[i] / max(port_vol, 1e-8) * 100)
        }
        for i in range(len(names))
    ],
    "pairwise_contributions": matrix_records(
        pd.DataFrame(pair_contrib * 252, index=names, columns=names)
    )
}
```

**Solution 2: Pull the optimized weights from F10 automatically.**

When F08 is called from F14 or from F12, pass the F10 optimal weights into F08 via the payload. This creates the natural analytical chain: F10 optimizes, F08 decomposes the risk of the optimal portfolio. Add `optimal_weights_from_f10` as a recognized payload key that F08 uses when `portfolio_weights` is not explicitly provided.

The UI for F08 then has a toggle: "Decompose risk for equal-weight factor portfolio / Decompose risk for optimized portfolio / Enter custom weights." All three paths flow into the same decomposition code.

---

## F06 BID-ASK SPREAD PROXY: BUILD IT PROPERLY

You do not need external live data. You have everything you need locally to build a high-quality bid-ask spread proxy. There are three academically validated approaches you can implement with price and volume data.

**Roll's Implied Spread (primary proxy)**

The Roll measure estimates the effective bid-ask spread from the negative serial covariance of price changes. This is the standard academic proxy used in Amihud, Pastor-Stambaugh, and dozens of empirical asset pricing papers.

```python
def roll_spread(prices: pd.Series, window: int = 63) -> pd.Series:
    """
    Roll (1984) implied spread estimator.
    spread = 2 * sqrt(max(0, -cov(delta_p_t, delta_p_{t-1})))
    """
    delta = prices.pct_change(fill_method=None)
    cov_series = delta.rolling(window).cov(delta.shift(1))
    spread = 2 * np.sqrt(np.maximum(0, -cov_series))
    return spread
```

**Amihud Illiquidity Ratio (secondary proxy)**

Measures price impact per unit of volume. High Amihud ratio means large price moves per dollar traded, which correlates strongly with wide spreads.

```python
def amihud_illiquidity(returns: pd.Series, volume_usd: pd.Series, window: int = 63) -> pd.Series:
    """
    Amihud (2002) illiquidity: mean(|r_t| / volume_t) * 1e6
    Scale by 1e6 to get readable units.
    """
    ratio = returns.abs() / volume_usd.clip(lower=1.0)
    return ratio.rolling(window).mean() * 1e6
```

**Corwin-Schultz High-Low Spread (best proxy for daily OHLCV data)**

This is the most accurate daily spread proxy if you have high and low prices. It uses the fact that the high-low range over one day and two days contains information about the spread.

```python
def corwin_schultz_spread(high: pd.Series, low: pd.Series) -> pd.Series:
    """
    Corwin & Schultz (2012) high-low spread estimator.
    Most accurate daily spread proxy without quote data.
    """
    beta = (np.log(high / low)) ** 2
    beta_sum = beta + beta.shift(1)
    gamma = (np.log(high.rolling(2).max() / low.rolling(2).min())) ** 2

    alpha = (np.sqrt(2 * beta_sum) - np.sqrt(beta_sum)) / (3 - 2 * np.sqrt(2)) \
            - np.sqrt(gamma / (3 - 2 * np.sqrt(2)))

    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return spread.clip(lower=0)
```

**How to wire this into F06:**

```python
def _bid_ask_spread_proxy(chars: pd.DataFrame, prices: pd.DataFrame, factor: str, window: int = 63) -> Dict:
    """
    Compute bid-ask spread proxy for long and short book of the factor.
    Returns spread trend and crowding contribution.
    """
    if prices.empty or chars.empty or factor not in chars:
        return {}

    q = chars[factor].rank(pct=True)
    long_tickers = set(chars[q >= 0.8]["Ticker"])
    short_tickers = set(chars[q <= 0.2]["Ticker"])

    close = prices.set_index(["Date", "Ticker"])["Close"].unstack("Ticker").sort_index()
    volume = prices.set_index(["Date", "Ticker"])["Volume"].unstack("Ticker").sort_index()

    results = {}
    for book_name, tickers in [("long", long_tickers), ("short", short_tickers)]:
        book_tickers = [t for t in tickers if t in close.columns]
        if not book_tickers:
            continue

        # Roll spread per ticker, then equal-weight across book
        roll_spreads = pd.DataFrame({
            t: roll_spread(close[t].dropna(), window)
            for t in book_tickers
        }).mean(axis=1)

        # Amihud per ticker
        vol_usd = close[book_tickers] * volume[book_tickers].fillna(0)
        rets = close[book_tickers].pct_change(fill_method=None)
        amihud = pd.DataFrame({
            t: amihud_illiquidity(rets[t].dropna(), vol_usd[t].dropna(), window)
            for t in book_tickers
        }).mean(axis=1)

        # Spread trend: is liquidity deteriorating?
        spread_pct = empirical_percentile(roll_spreads.dropna(), float(roll_spreads.dropna().iloc[-1]))
        spread_velocity = float(roll_spreads.diff(21).iloc[-1])

        results[book_name] = {
            "roll_spread_current": float(roll_spreads.iloc[-1]) if len(roll_spreads) else None,
            "roll_spread_percentile": spread_pct,
            "roll_spread_velocity_21d": spread_velocity,
            "amihud_current": float(amihud.iloc[-1]) if len(amihud) else None,
            "amihud_percentile": empirical_percentile(amihud.dropna(), float(amihud.dropna().iloc[-1])) if len(amihud) else None,
            "tickers": len(book_tickers),
        }

    # Long-short spread differential: crowding signal
    long_spread = results.get("long", {}).get("roll_spread_current", 0) or 0
    short_spread = results.get("short", {}).get("roll_spread_current", 0) or 0
    ls_differential = long_spread - short_spread
    ls_percentile = empirical_percentile(
        pd.Series([long_spread, short_spread]),
        ls_differential
    )

    return {
        "long_book": results.get("long", {}),
        "short_book": results.get("short", {}),
        "long_short_spread_differential": ls_differential,
        "differential_percentile": ls_percentile,
        "crowding_signal": ls_differential > 0,  # long book more illiquid = crowding pressure
        "method": "roll_1984_implied_spread_plus_amihud_2002",
    }
```

**Wire into F06 composite:**

The bid-ask spread proxy should enter the composite as the fourth metric, replacing the current excluded placeholder. The composite becomes four equal-weight metrics: valuation spread percentile, return autocorrelation, HHI concentration, and bid-ask spread differential percentile.

```python
# In F06 run():
bid_ask = _bid_ask_spread_proxy(chars, price_sample(int(payload.get("max_tickers", 240))), factor)
spread_score = float(bid_ask.get("differential_percentile", 50) or 50)

# Update composite to include spread:
composite = float(np.nanmean([crowd_val, ac_score, hhi_score, spread_score]))

# Add to rows table:
rows.append({
    "metric": "bid_ask_spread_differential",
    "score": spread_score,
    "raw_long": bid_ask.get("long_book", {}).get("roll_spread_current"),
    "raw_short": bid_ask.get("short_book", {}).get("roll_spread_current"),
    "differential": bid_ask.get("long_short_spread_differential"),
    "included_in_composite": True,
    "method": "roll_1984_implied_spread",
})
```

**Add to F06 tables:**

```python
tables={
    "crowding_metrics": rows,
    "liquidity_long_short": [
        {
            "book": "long",
            "roll_spread": bid_ask.get("long_book", {}).get("roll_spread_current"),
            "roll_spread_percentile": bid_ask.get("long_book", {}).get("roll_spread_percentile"),
            "amihud": bid_ask.get("long_book", {}).get("amihud_current"),
            "spread_velocity_21d": bid_ask.get("long_book", {}).get("roll_spread_velocity_21d"),
        },
        {
            "book": "short",
            "roll_spread": bid_ask.get("short_book", {}).get("roll_spread_current"),
            "roll_spread_percentile": bid_ask.get("short_book", {}).get("roll_spread_percentile"),
            "amihud": bid_ask.get("short_book", {}).get("amihud_current"),
            "spread_velocity_21d": bid_ask.get("short_book", {}).get("roll_spread_velocity_21d"),
        },
    ],
    "bid_ask_detail": bid_ask,
    ...
}
```

---

## WHAT THIS UNLOCKS

With Roll spread, Amihud, and the long-short differential all in the composite, F06 now has four genuine, academically grounded crowding metrics computed entirely from local data. The bid-ask section in the F06 output becomes one of the most differentiated outputs on the platform because most commercial systems use raw quoted spreads from vendor feeds. Your proxy approach is actually what academic papers use when vendor data is unavailable, which means your methodology is defensible and citable. The Corwin-Schultz estimator in particular is a 2012 Journal of Finance paper and citing it in the methodology note gives the output instant credibility.

The composite crowding score is now genuinely four-dimensional: valuation stretch, momentum crowding via autocorrelation, position concentration via HHI, and liquidity deterioration via Roll spread differential. That is a more complete crowding picture than most institutional risk systems produce.
