# Quant360 PCA V2 Backend

Backend-only PCA V2 implementation. No routes or frontend wiring were changed.

## Data Verification

- [x] `backend/data/market_universe.parquet` exists and was verified: 10,760,544 OHLCV rows with `Ticker`, `Date`, `Open`, `High`, `Low`, `Close`, `Volume`.
- [x] `backend/data/market_universe_hourly.parquet` exists and was verified: 122,113 hourly OHLCV rows across 23 tickers.
- [x] `backend/data/prices` exists and was verified: 3,079 local daily price files across equities, FX, crypto, futures, ETFs, indices and proxies.
- [x] Intraday CSV directories were verified: 22 backend hourly CSV files and 28 root hourly CSV files.
- [x] `backend/data/portfolio_state.json` exists and was verified: server-side cash, holdings and trade history snapshot.
- [x] `factors/data/processed/category7_macro_regime.parquet` exists and was verified: VIX, rates, yield curve, credit and VIX term structure fields.
- [x] `backend/data/fundamentals/master_fundamentals.parquet` exists and was verified: sector, industry, market cap and currency metadata are available.
- [x] Numerical stack verified: `numpy`, `pandas`, `sklearn`, `scipy`, `cvxpy`, `polars`, `pyarrow`, `joblib`, `yfinance`.
- [x] Added append-only `core/data_pooling.py` for local price-file discovery, dry-run cross-asset append reports, optional yfinance symbol fetches, and FRED series. Runtime feature calls are read-only.

## Missing Data Checklist

- [x] Daily equity OHLCV for a large listed universe is present in `backend/data/market_universe.parquet`.
- [x] Equity dollar volume proxy is present through `Close * Volume`.
- [x] Sector, industry, market cap, and currency metadata are present in `backend/data/fundamentals/master_fundamentals.parquet`.
- [x] VIX, Treasury rates, yield curve, credit spreads, and VIX term structure fields are present in `factors/data/processed/category7_macro_regime.parquet`.
- [x] FX spot daily files are present locally for 15 of the 17 PCA V2 target FX pairs. Major FX coverage is complete; missing target FX pairs are `USDTRY=X` and `USDCNH=X`.
- [x] Futures daily files are present locally for all 21 PCA V2 target futures symbols across energy, metals, agriculture, and rates.
- [x] Crypto daily files are present locally for all 11 PCA V2 target crypto symbols.
- [x] Intraday hourly data is present: `backend/data/market_universe_hourly.parquet` plus hourly CSV source folders.
- [x] Server-side persisted holdings snapshot exists in `backend/data/portfolio_state.json`.
- [ ] Clean standalone cross-asset PCA blocks are not materialized as separate FX/futures/crypto parquet panels yet. The data exists in `market_universe.parquet` and/or `backend/data/prices`, but V10 still needs a dedicated block loader/materialization pass before claiming production-grade hedged block decomposition.
- [ ] Roll-adjusted continuous futures methodology is not verified. Raw/local futures files exist; roll rules and contract stitching are not audited.
- [ ] Order-flow, signed volume, bid/ask spread, tick-level trades, and true market microstructure fields are not present. Exact Kyle lambda and spread analytics remain unavailable from current files.
- [ ] Shares-outstanding time series is not present as a clean daily panel. Static/latest fundamentals exist; turnover ratio requiring daily float/shares history is not fully covered.
- [ ] Multi-currency FX hedge exposure matrix is not present as a structured holdings-currency matrix. FX prices exist; hedge exposure mapping still needs portfolio currency exposure data.
- [ ] Durable portfolio holdings history is not present as parquet/DB. A JSON server-side state file exists, but long-term historical holdings/equity curve persistence is not complete.

## Cross-Asset Coverage Audit

- [x] Target cross-asset symbol count: 49.
- [x] Present in `backend/data/market_universe.parquet`: 47 of 49.
- [x] Present as local files in `backend/data/prices`: 47 of 49.
- [ ] Missing target symbols: `USDTRY=X`, `USDCNH=X`.
- [x] Dry-run local append path verified: `append_cross_asset_prices_to_master(dry_run=True)` finds 103,475 candidate rows and would fetch only `USDTRY=X`, `USDCNH=X` if run with `dry_run=False`.

Operator examples:

```bash
PYTHONPATH=backend python3 - <<'PY'
from app.services.pca_v2.core.data_pooling import cross_asset_missing_report, append_cross_asset_prices_to_master
print(cross_asset_missing_report()["missing_from_master"])
print(append_cross_asset_prices_to_master(dry_run=True))
PY
```

To mutate later, call `append_cross_asset_prices_to_master(dry_run=False)`. The helper appends and deduplicates; it does not blindly overwrite the master parquet.

## Implemented Feature Checklist

- [x] V01 RMT Noise-Filtered Covariance Engine
  - Sample/Ledoit-Wolf/OAS/EWMA/MCD covariance estimators.
  - Marchenko-Pastur threshold, signal/noise classification, scree cutoffs.
  - RMT-cleaned covariance reconstruction with diagonal idiosyncratic variance.
  - Raw, cleaned and difference heatmap records.
  - Condition number diagnostics and audit trail.

- [x] V02 PCA Factor Extraction and Loading Matrix
  - PCA loading matrix, factor return time series, explained variance.
  - Varimax rotation path when requested.
  - Top positive/negative loading tables.
  - Sector cluster map and heuristic PC interpretation labels.

- [x] V03 PCA Portfolio Risk Decomposition and Attribution
  - PC factor variance decomposition plus idiosyncratic residual.
  - Marginal risk contribution by position.
  - VaR/CVaR decomposition, historical VaR/CVaR and Cornish-Fisher VaR.
  - Rolling portfolio volatility output.

- [x] V04 PCA Residual OU Statistical Arbitrage Signal Engine
  - Residual construction from PCA factor model.
  - OU/AR(1) parameter estimation.
  - Residual Z-score ranking, half-life filter, long/short/no-signal classification.
  - Trade list and OU parameter tables.

- [x] V05 Rolling Eigenvalue Stability and Regime Transition Monitor
  - Multi-window rolling PCA metrics.
  - PC1 share, effective dimensions, eigenvector cosine stability.
  - CUSUM structural-break table.
  - Eigenvalue-ratio K monitor.
  - Multi-frequency tensor proxy implemented; full Tucker decomposition is not included in this pass.

- [x] V06 Constrained PCA Portfolio Optimization with RMT Covariance
  - CVXPY/OSQP constrained optimization when available.
  - Long-only or gross-exposure long/short constraints.
  - Efficient frontier sweep.
  - Optimal weights and risk contribution table.
  - Robust frontier proxy included; full Bertsimas-Brown worst-case robust counterpart is not complete in this pass.

- [x] V07 Out-of-Sample Bootstrap Validation and Factor Genuineness Scorecard
  - Case bootstrap over the returns matrix.
  - Eigenvalue confidence bands vs MP threshold.
  - Eigenvector cosine stability scorecard.
  - Bai-Ng criteria proxy and principal-angle proxy.
  - Block bootstrap is documented but not fully implemented in this pass.

- [x] V08 PCA Residual Cross-Correlation and Contagion Monitor
  - Residual correlation matrix.
  - Residual lambda1 monitor.
  - Sector/group residual correlation rows.
  - Top residual-correlation pair table.
  - Under-specification diagnostic across K.

- [x] V09 PCA Stress Scenario Generator and PC-Shock P&L Attribution
  - 2K +/- sigma PC shock scenarios.
  - Portfolio P&L by scenario.
  - Position-level P&L waterfall per scenario.
  - Historical analog finder in normalized PC-score space.
  - Stress VaR/CVaR from scenario P&L distribution.
  - PDF export not generated in this backend-only pass.

- [x] V10 Cross-Asset RMT Covariance Engine with Hedged Block Decomposition
  - [x] Real covariance/block decomposition over currently available local OHLCV symbols and ETF/index proxies is implemented.
  - [x] Asset-class contribution by PC is computed.
  - [x] Data-gap report is emitted.
  - [x] Repo-wide scan confirmed broad local FX, futures, crypto, intraday and portfolio-state data availability.
  - [x] Dedicated runtime block loader now reads equities, FX, commodity futures, rates futures and crypto from `market_universe.parquet` and `backend/data/prices`.
  - [x] FX EWMA, futures/rates OAS, crypto robust covariance fallback, DCC conditional correlation, FX hedge ratios, CASCI, stress overlays and hourly inventory are implemented.
  - [ ] Independent roll-adjusted futures methodology is not verified. Raw continuous/proxy futures files are used.

- [x] V11 Latent Liquidity Factor Extraction and Illiquidity-Adjusted Risk
  - Amihud illiquidity panel from local Close x Volume dollar volume.
  - Latent liquidity factor via PCA of standardized illiquidity panel.
  - Liquidity beta ranking table.
  - Liquidation cost map using square-root impact.
  - Liquidity-adjusted VaR and quant unwind score.

## Stable Backend Contract

Every feature returns:

```python
{
    "feature_id": "feature_XX",
    "status": "ok|partial|warning|error",
    "summary_cards": [],
    "charts": {},
    "tables": {},
    "alerts": [],
    "meta": {},
}
```

Use `app.services.pca_v2.registry.run_feature(feature_id, payload)` to execute a feature.

## Smoke Test

Completed successfully with:

```bash
python3 -m compileall -q backend/app/services/pca_v2
PYTHONPATH=backend python3 - <<'PY'
from app.services.pca_v2.registry import run_feature
payload = {
  "symbols": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","JPM","XOM","UNH","WMT","SPY","QQQ"],
  "lookback_days": 252,
  "max_symbols": 12,
  "compute_mode": "realtime",
}
for fid in [f"{i:02d}" for i in range(1, 12)]:
    out = run_feature(fid, payload)
    print(fid, out["status"], list(out["charts"])[:3], list(out["tables"])[:3])
PY
```

All features returned successfully. V10 now returns `ok` with live local cross-asset blocks.

## Honest Remaining Work

- [x] Add a dedicated V10 block loader over existing `market_universe.parquet`/`backend/data/prices`.
- [ ] Materialize dedicated futures, FX and crypto OHLCV panels as canonical parquet files.
- [ ] Fetch or otherwise source the two missing target FX pairs: `USDTRY=X`, `USDCNH=X`.
- [ ] Add true block bootstrap/stationary bootstrap to V07 if research mode requires formal autocorrelation-preserving resampling.
- [ ] Add full Tucker/tensor decomposition for V05/V08 multi-frequency regime/residual tensors.
- [ ] Add report/PDF export for V09 once API/frontend export surface is planned.
- [ ] Wire API routes only when requested. This pass did not touch routing.
