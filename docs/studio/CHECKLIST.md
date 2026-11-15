# Studio v3 checklist

Tick as work lands. Each phase ends with tests green, screenshots at 1440 and 1024, a commit and a push. Plan: [PLAN.md](PLAN.md) §7.

## Phase 0: data and engine spike
- [ ] Measure hourly bars: symbols, date range, gaps (`market_universe_hourly.parquet`, `intraday_hourly_v5`)
- [ ] Measure delisted share of the daily universe; print it in limits
- [ ] Check non-equity coverage (crypto, forex) via Screener's non-equity loader
- [ ] Vector engine: SMA cross, 500 names, 10 years under 50 ms (numba)
- [ ] Event engine: same strategy, trade-for-trade match with vector engine (test)
- [ ] Merge the three `performance.py` / `stats.py` copies into one `metrics.py`; other labs green

## Phase 1: backtest end to end
- [ ] `studio_v3` package, registry, manifest, jobs API (`/api/studio-v3/...`)
- [ ] Strategy spec (pydantic) + formula compile (shared `signal_lang`)
- [ ] Fill model: next open default, same close switch, stops/limits in bar, gap fills, conservative same-bar rule
- [ ] Costs: commission, slippage, borrow, dividends on shorts, volume cap
- [ ] Metric set (FEATURES_AND_OUTPUTS §4) with exact-number tests
- [ ] `studioLab.ts`, routes, nav, Home placeholder
- [ ] Backtest page: hero, KPIs, equity/drawdown, returns, trade list, carried by, fill check, crisis events, capacity, limits
- [ ] "Honest order" layout; best-months toggle; first vs last third rolling Sharpe
- [ ] Visual baselines added

## Phase 2: Build
- [ ] Blocks editor ⇄ formula
- [ ] Python in Docker sandbox (no network, read-only, non-root, caps, `ast` screen)
- [ ] Plain English → formula (review before run)
- [ ] Repaint check (50 cuts) and lint, live
- [ ] Trial counter
- [ ] My limits (walk-away conditions) and Stated regime, saved with the version
- [ ] Versions, immutable, diff
- [ ] Templates (20)
- [ ] Test: same rule as blocks, formula and Python gives identical trades

## Phase 3: optimise and validate
- [ ] Optimise: grid, random, Optuna; map, surface, stability, top sets, Pareto, importance
- [ ] Walk-forward: anchored and rolling, purge and embargo, WF matrix, WFE, drift
- [ ] Robustness: vs random, MCPT, noise, vs shifted, vs others, delay, cost shock, liquidity, parameter permutation, variance, data source
- [ ] Monte Carlo: reshuffle, resample, block, trade skip, randomized exits, ruin
- [ ] Overfitting: PSR, DSR (trial count), PBO/CSCV, CPCV, min track record, haircut, hold-out log
- [ ] Verdict grade with reasons and cheapest fix
- [ ] Test: planted overfit strategy flagged; known-robust strategy passes

## Phase 4: chart
- [ ] `StudioChart` on lightweight-charts 5, `/bars` only
- [ ] Indicators ported and tested
- [ ] Drawings ported, saved on server
- [ ] Strategy overlay, trade navigator, replay
- [ ] Patterns with "not found" legend
- [ ] Server alerts
- [ ] `/trade` redirects here

## Phase 5: understand and live signals
- [ ] Regimes: trend, vol, drawdown, HMM, seasonality, trades per regime, conditions
- [ ] Combine: correlation, allocation methods, marginal contribution, overlap
- [ ] Signals today: table, near triggers, map

## Phase 6: paper and certify
- [ ] Paper: freeze, daily EOD step from parquet, MC band, drift alerts to Monitor, kill switch, limits
- [ ] Paper decay panel: power statement, cost leak, signal IC, drawdown odds, sizing from evidence, shadow book
- [ ] Certify: server re-run, hash compare, one-page PDF, share link and embed

## Grand-stage additions (FEATURES_AND_OUTPUTS §9; phase in brackets)
- [ ] G9 India coverage measured [0]
- [ ] G13 Agent API and MCP tool [1+]
- [ ] G6 ML and Research signals as blocks [2] · G8 bring my own data [2] · G12 research notebook [2]
- [ ] G5 prop-firm and risk rules [3] · G11 AI reviewer [3] · G14 impact and capacity curve [3] · G15 stress scenarios [3]
- [ ] G2 manual replay practice + journal [4]
- [ ] G1 alerts and webhooks [5] · G7 meta strategies [5] · G10 tax-aware results [5]
- [ ] G3 import my real trades [6] · G4 verified strategy gallery [6]

## Phase 7: remove old Studio
- [ ] Graph + `rg` + route checks + smoke test (AGENTS.md)
- [ ] Delete `app/studio_v2`, `routers/studio.py`, `services/studio`, `components/studio`, `stores|hooks|lib/studio*`, `chart_engine`, old Studio tests

## Phase 8: phone
- [ ] Bottom nav, settings sheet, card rows (with Screener phone-1)

## Decisions for the owner
- [ ] Pyodide (MPL-2.0) for in-browser Python preview: default no
- [ ] OpenBB licence conflict (Apache vs AGPL): default not used
- [ ] `arch` licence file missing on GitHub: check before relying on it beyond the existing install
- [ ] Live broker trading: out of v3
