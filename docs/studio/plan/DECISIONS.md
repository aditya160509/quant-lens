# Studio decisions and data limits

What the data can and cannot support, and what Studio does about it. Source: `limits.audit()` on data version `fe627079`, run 2026-11-16.

## What the data is

| Fact | Value | Effect |
|---|---|---|
| Daily tickers | 4,157 | Fine for US equities |
| Real history | 2015 onward (3,551 names in 2015; 1–3 names before 2014) | About 11 years. No 2000 or 2008 bear market for stocks |
| Last bar | 2026-02-01 for most names (288 days old) | Nothing "today" is real |
| Delisted names | 55 ended early (1.3%) | Survivorship bias: dead names are mostly missing |
| Price adjustment | Mixed: older segments raw, newer ones dividend-adjusted | Returns and total-return comparisons are approximate |
| Dividends, splits columns | None | No dividend charge on shorts, no real total return |
| Hourly bars | Not used by Studio (removed 2026-11-16) | Daily only |
| Fundamentals | From 2021, 90-day filing lag | 5 years only |
| India and non-equity | Not measured | Unknown |

## Remove or hide until phase 9 (the data refresh)

| Feature or output | Page | Why | Decision |
|---|---|---|---|
| Crisis strip rows before 2015 (dot-com, 2008, 2011) | Backtest › Returns | No stock bars then | Show only 2015+ events (2018 Q4, 2020 Covid, 2022 rates) |
| Live › Today signals, paper fills, order CSV, distance to trigger | Live | Data is 288 days old | Disable with "data ends 2026-02-01" until the daily update job runs |
| Alerts and daily digest | Live | Same: would fire on stale bars | Do not ship until the daily update job exists |
| Dividend charge on shorts | Costs | No dividend column | Leave off; say so in the costs line (already done) |
| Fundamentals in rules before 2021 | Build | No data | Refuse formulas that read fundamentals for dates before 2021 |
| India cost profile (dated STT) | Library | Coverage unmeasured | Not built until India coverage is measured |
| "Full" validation profile on short universes | Validate | 8 walk-forward windows on 11 years leaves ~1-year windows | Keep, but CPCV and the matrix already skip cells under 40 bars a group |

## Keep, but label as limited

| Output | Page | Label |
|---|---|---|
| Survivorship delta | Backtest | "Understated: only 1.3% of names delisted in this data" |
| Net return vs benchmark, total return | Backtest, Portfolio | "Prices are mixed raw and dividend-adjusted" |
| Hold-out | Validate | Hold-out is the last part of 2015–2026, so it has no deep bear market |
| Power card, track record years | Validate | Uses 11 years at most; many ideas cannot reach 80% power here |
| Regime labels | Backtest | Regimes from 2015 onward only |
| Shocks (gap, volatility ×3, move with market) | Validate | Synthetic, not history; labelled as shocks |
| PBO, CPCV, walk-forward matrix | Validate | Need 2+ settings; skipped with a reason otherwise |

## Decisions already taken

- 2026-11-16: hourly bars removed from Studio (bar magnifier, fill check, 1h chart bars, hourly audit). Yahoo keeps only 730 days of hourly bars: too short for walk-forward or luck tests, and held for 23 indices, no stocks. A stop and a target inside one bar now always fill the stop first (worst case). Saved runs that still carry `magnifier` load fine; the field is dropped on read. `data_version` no longer changes when the hourly file changes.
- 2026-11-15: old Studio removed; Studio Chart embeds the full `chart_engine` chart (owner ask).
- `/trade` is not redirected to `/studio/chart`: it is a multi-tab trading page.
- Docker sandbox for Python strategies deferred (owner: "keep for later"); Python runs in a locked child process instead.
- Portfolio weights default to in-sample and say so; quarterly re-estimation on the trailing year is the honest option.
- The PBO rank scatter was replaced by in-sample vs out-of-sample Sharpe of the winner: the winner's in-sample rank is always top, so the scatter said nothing.

## Open owner decisions

See CHECKLIST "Decisions for the owner": Pyodide, OpenBB licence, `arch` licence, Pine import.
