# Screener V2 Feature Implementation Checklist

- [x] Read `screener features.md` end to end.
- [x] Verified local data availability before building.
- [x] Created `screener_v2` service folder.
- [x] Created reusable local parquet data loader.
- [x] Created shared analytics module.
- [x] Created append-only missing-data fetcher scaffold.
- [x] Created package registry and manifest.
- [x] Implemented S1 Core Multi-Factor Screener Engine.
- [x] Implemented S2 Formula Builder and Custom Expression Screener.
- [x] Implemented S3 Composite Quant Score Engine.
- [x] Implemented S4 Academic Strategy Screener Library.
- [x] Implemented S5 Screener Backtester with Point-in-Time Validation outputs.
- [x] Implemented S6 Alert Engine and Watchlist Monitor outputs.
- [x] Implemented S7 Comparative Relative Valuation Screener.
- [x] Implemented S8 Screener Result Export and Integration Layer.
- [x] Compiled package successfully.
- [x] Smoke-ran all eight features successfully.

## Not Fully Production-Complete

- [ ] Saved screens persistence: output key exists, but no database/API route is wired.
- [ ] Persistent alerts and notifications: current run emits alert candidates only.
- [ ] Point-in-time fundamentals: fetcher scaffold exists, but local PIT-asof panel is not present.
- [ ] Delisted security history: fetcher scaffold exists, but local delisting panel is not present.
- [ ] Historical change reports across runs: requires screen run history storage.
- [ ] API routes: intentionally not wired in this pass.
