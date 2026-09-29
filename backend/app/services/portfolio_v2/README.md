# Portfolio V2 Backend

Portfolio V2 is a backend-only service scaffold and implementation pass. It is not wired to API routes yet. The implementation uses local parquet data first:

- `backend/data/market_universe.parquet` as the main daily OHLCV source.
- `backend/data/market_universe_hourly.parquet` or the larger research hourly parquet when hourly is requested.
- `backend/data/canonical/{equity,fx,crypto,futures}_daily.parquet` for cross-asset panels.
- `backend/data/canonical/portfolio_holdings_history.parquet` for server-side current holdings when user weights are not supplied.
- `factors/data/processed/category7_macro_regime.parquet` for VIX/rates/credit macro drivers.
- `backend/data/fundamentals/master_fundamentals.parquet` for sector and market-cap metadata.

## Numbering Normalization

`portfolio features.md` skips feature numbers 11 and 14 in headings, but the architecture section says the cleaned stack has 13 features. This backend normalizes to:

- F01-F10 match the document headings.
- F11 implements document Feature 12: Optimal Execution and Transaction Cost.
- F12 implements document Feature 13: Systemic Risk and Fire-Sale Contagion.
- F13 implements document Feature 15: Multi-Strategy Portfolio Allocation.

## Checklist

[x] F01 Portfolio Construction Engine: shrinkage covariance, GMV, max Sharpe, inverse-vol, risk parity, max diversification, HRP-style ordering, efficient frontier, risk contribution, constraint report.

[x] F02 Honest Backtesting Engine: gross/net return series, transaction-cost drag, equity/drawdown, monthly heatmap, PSR/DSR, walk-forward folds, explicit survivorship data limitation.

[x] F03 Performance Attribution Engine: Brinson-Fachler sector attribution, asset contribution waterfall, active return series, drawdown attribution, risk attribution, skill-vs-luck t-stat.

[x] F04 Stress Testing and Scenario Engine: historical quantile replay, component waterfall, reverse stress threshold, correlation stress, Monte Carlo distribution.

[x] F05 Market-Implied Macro Factor Model: VIX/rates/credit macro exposure regression from category7 macro parquet, rolling exposure, unintended macro bet flags.

[x] F06 Regime Detection and Regime-Aware Allocation: GMM regime fit when available, volatility fallback, transition matrix, regime performance, conditional weight scale.

[x] F07 Liquidity Analytics Engine: Amihud proxy, dollar ADV, days-to-liquidate at 15% ADV, LVaR proxy, liquidation schedule, half-life.

[x] F08 Correlation, Diversification and Contagion Network: correlation heatmap, crisis delta matrix, eigenvalues, effective number of bets, network edges.

[x] F09 Alpha Decay and Factor Half-Life Engine: empirical cross-sectional IC decay, half-life, decay-adjusted weight curve, crowding dispersion proxy.

[x] F10 Growth-Optimal Position Sizing Engine: multi-asset Kelly, constrained Kelly, current sizing gap, growth frontier, ruin probability surface, turnover-optimal Kelly fraction.

[x] F11 Optimal Execution and Transaction Cost Engine: pre-trade impact estimate, implementation shortfall frontier, per-day execution schedule, joint schedule over assets.

[x] F12 Systemic Risk and Fire-Sale Contagion Engine: portfolio overlap heatmap using generated peer proxies, fire-sale impact table, DebtRank-style exposure score, contagion network.

[x] F13 Multi-Strategy Allocation and Risk Budgeting Engine: deterministic strategy proxies, strategy correlation matrix, inverse-vol dynamic allocation, risk budget, kill switch, Kelly strategy weights.

[x] Shared loader: full market universe parsing, canonical cross-asset panels, hourly support, frequency-aware lookback, holdings-history fallback weights, macro/fundamental metadata.

[x] Fetcher folder: append-only missing-data helper and explicit inventory of datasets required to complete non-local-data outputs.

## Honest Gaps

[ ] Point-in-time constituents are not present. F02 can run and audits the issue, but cannot remove survivorship bias without historical membership data.

[ ] True factor ETF AUM history is not present. F09 uses cross-sectional dispersion as a live crowding proxy and marks ETF AUM crowding as unavailable.

[ ] Actual peer fund holdings are not present. F12 computes overlap/fire-sale risk from deterministic peer proxies; real DebtRank needs peer books or parsed 13F holdings.

[ ] Strategy-level position books are not present. F13 computes strategy return allocation, but inter-strategy netting is marked data-limited until per-strategy asset holdings exist.

[ ] Full Almgren-Chriss cross-impact Riccati solution is not implemented. F11 computes a defensible square-root impact and timing-risk pre-trade TCA from daily OHLCV/ADV.

[ ] Options/implied volatility inputs are not used. The portfolio spec did not require options for the cleaned stack, and the repo data is daily OHLCV/macro first.

## API Wiring Notes

Each feature exposes `run(payload: dict | None) -> dict` and returns:

```json
{
  "feature_id": "feature_01",
  "status": "ok",
  "summary_cards": [],
  "charts": {},
  "tables": {},
  "alerts": [],
  "meta": {
    "symbols": [],
    "lookback_days": 756,
    "frequency": "daily",
    "compute_mode": "realtime",
    "access_issues": []
  }
}
```

Route wiring can mirror `factors_v2`: dynamically import `backend.app.services.portfolio_v2.features.feature_XX` and call `run(payload)`.
