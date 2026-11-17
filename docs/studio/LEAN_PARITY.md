# LEAN parity: making every Studio number match a verified engine

Goal: every price, fill, cost, position, equity point and statistic Studio produces matches what QuantConnect LEAN produces on the same data and the same rules, within stated tolerances, proven by automated tests. LEAN (Apache 2.0) is the oracle; Studio keeps its own fast engines.

Companion files: `CODE_STANDARDS.md` (gates and severities), `LEAN_REUSE.md` (formula list), `DECISIONS.md` (data limits).

## 1. Decision: oracle, not replacement

| Option | Verdict |
|---|---|
| A. Replace Studio's engines with LEAN | No. LEAN is C# in Docker, ~10–30 s start per run, no numba sweeps (a 400-cell sweep or 1,000-path robustness run would take hours), and it needs its own data format for every request |
| B. Port LEAN formulas by reading code only | Not enough. Reading gives the formula, not proof; ordering and edge cases (gaps, splits, cash, rounding) are where engines differ |
| **C. Port the semantics, then prove them against real LEAN runs** | **Chosen.** Studio stays fast; LEAN runs offline as a test oracle on fixed fixtures; any difference is a failing test |

Available on this machine: Docker 28.3.3 and the `lean` CLI (PyPI `lean` 1.0.233). The oracle runs only in tests and CI, never on a user request, so the deferred Docker sandbox decision is unaffected.

## 2. How it works

```
fixtures (frozen OHLCV, small universes)
        │
        ├── to_lean.py ──► LEAN daily format ──► lean backtest (Docker) ──► orders.json, equity.json, statistics.json
        │                                                                      │
        └── Studio vector + event engines ─────────────────────────────────────┤
                                                                               ▼
                                                          parity.py compares field by field
                                                          → tests/test_studio_v3_lean_parity.py
```

1. **Fixtures.** `backend/tests/fixtures/lean/`: frozen bars for 3 universes (1 symbol, 10 symbols, 50 symbols incl. one delisting and one gap-heavy name), 2015–2025, stored as parquet and committed. They are never fetched live, so results cannot drift.
2. **Converter `to_lean.py`.** Writes LEAN's daily equity format: `equity/usa/daily/<sym>.zip` holding a CSV `yyyyMMdd 00:00,open*10000,high*10000,low*10000,close*10000,volume`, plus a `map_files` entry and a flat `factor_files` row (factor 1, 1), because our prices are already adjusted (see §5). Market hours database and the US holiday calendar come from LEAN's own `Data/` folder.
3. **Algorithm templates.** One LEAN Python algorithm per Studio rule shape, generated from the same `Strategy` spec: signal entry/exit, stop and target, trailing stop, time stop, ranked rotation of N slots, % equity / fixed cash / risk sizing, long-short. Each sets `DataNormalizationMode.Raw` (our series are already adjusted), `Resolution.Daily`, the matching fee, slippage and fill models, and `set_benchmark`.
4. **Oracle run.** `lean backtest` in Docker writes results JSON. The outputs are cached by hash of (fixture, algorithm, LEAN image tag) in `tests/fixtures/lean/golden/`, so normal test runs read the goldens and need no Docker. A `--refresh-lean` flag reruns the oracle; the LEAN image tag is pinned.
5. **Comparison `parity.py`.** Matches orders by (symbol, date, direction) and compares quantity, fill price, fee, then daily equity and every statistic, with the tolerances in §4. It prints the first divergence with both engines' state on that bar.

## 3. Semantics to align (each is a P0 or P1 item under `CODE_STANDARDS.md`)

Studio behaviour today (from `core/engine.py`, `core/fills.py`) against LEAN's documented behaviour. "Verify" means the golden test decides; the LEAN source line is cited in the test.

| # | Area | LEAN (daily resolution) | Studio now | Action |
|---|---|---|---|---|
| 1 | Signal timing | `on_data` sees the bar after it closes; a market order placed then is submitted while the market is closed and is converted to **market-on-open**, filling at the next bar's official open | Next-open mode: signal at close t, fill at open t+1 | Same. Golden test |
| 2 | Same-close fills | Only via `market_on_close_order` placed before close, which needs intraday data | Optional "same close" mode | Keep but label it as optimistic; LEAN parity tests run next-open only |
| 3 | Stale data | Daily: a market order waits for the next bar | Missing bar → `_fill_gaps` | Verify that a halted or missing day defers the fill rather than filling at the old price |
| 4 | Stop market, gap through | Fills at the bar's open when it gaps past the stop, else at the stop (`EquityFillModel.StopMarketFill`) | `exit_check`: gap → open, else stop | Same; confirm with the gap-heavy fixture |
| 5 | Stop and target in one bar | LEAN has no bracket; two separate orders, whichever its fill loop processes first | Stop first (worst case) | Keep stop-first; parity template places the stop before the target to match |
| 6 | Limit orders | Buy fills if low < limit at min(limit, open); sell if high > limit at max(limit, open); order placed in a bar can't fill on that bar | Targets as limits | Align: no fill on the bar the order was placed |
| 7 | Slippage | Applied to fill price after the fill model; models `ConstantSlippageModel`, `VolumeShareSlippageModel`, `MarketImpactSlippageModel` | bps + share of bar range | Add LEAN models as named options; keep ours as "bar range" |
| 8 | Fees | Per order from the brokerage model (e.g. IB: $0.005/share, $1 min, 1% cap) | bps + per-share with minimum | Add the IB model exactly; tests per edge (min, cap) |
| 9 | Share rounding | Quantities rounded to the lot size (1 share) toward zero; `calculate_order_quantity` uses `free_portfolio_value_percentage` 0.0025 buffer | Fractional or floor? Verify | Integer shares by default; a cash buffer setting matching LEAN's 0.25% |
| 10 | Buying power | Cash account: no buy beyond cash; margin account: 2x overnight on US equities | Verify | Add account type; refuse orders above buying power the way LEAN marks them `Invalid` |
| 11 | Shorting | Margin required; borrow cost via `ShortableProvider` and fee model; no dividend charge in daily raw mode | Borrow bps | Keep borrow; state no dividend charge (`DECISIONS.md`) |
| 12 | Delisting | `Delisting` event: warning, then position liquidated at last price | Delisting settle at close | Same; golden test on the delisted fixture name |
| 13 | Order of the day | Fills at open, then `on_data` at close; equity marked at close | Steps 1–5 in `engine.py` docstring | Same order; golden equity curve proves it |
| 14 | Equity and returns | Portfolio value = cash + Σ qty × close; daily return from that series | Same | Golden equity to the cent |
| 15 | Statistics | `Statistics.cs`, `PortfolioStatistics.cs`: Sharpe on daily returns ×√252 with rf from `InterestRateProvider` (set to 0 in parity runs), PSR with SR* = 1/√252, drawdown, CAGR on days/365, alpha, beta, IR, tracking error, Treynor, expectancy, win/loss, VaR | Partial set | Port all; match to 1e-6 relative |
| 16 | Benchmark | `set_benchmark(symbol)` uses that symbol's close series | Benchmark series | Same symbol in both |
| 17 | Calendar | LEAN market hours database, NYSE holidays | Panel dates | Fixtures share one calendar; a test asserts no trading on LEAN holidays |
| 18 | Warm-up | `set_warm_up(n)` and indicators not ready before n bars; no orders during warm-up | Indicator NaNs at start | Assert no signal before the lookback is full, matching LEAN's `IsReady` |
| 19 | Indicators | LEAN's SMA, EMA (α = 2/(n+1), seeded with SMA), RSI (Wilder), ATR (Wilder), Bollinger (population std) | `formula.py` | Golden values per indicator from LEAN's own test CSVs (`Tests/TestData/spy_*.txt`), 1e-8 tolerance |
| 20 | Rounding and money | Decimal arithmetic, prices to the tick | float64 | Keep float64; compare with tolerances in §4; never round inside the engine, only for display |

## 4. Tolerances

| Quantity | Tolerance | Why |
|---|---|---|
| Order set (symbol, date, side) | Exact | Any extra or missing trade is a logic difference |
| Quantity | Exact (integers) | |
| Fill price | 1e-9 relative | Same formula, float vs decimal |
| Fee | $0.01 | Decimal rounding |
| Daily equity | 1e-6 relative, and a final equity within $1 on $100k | Accumulated float error |
| Statistics | 1e-6 relative; Sharpe and PSR 1e-4 | Sample vs population choices must match exactly, not loosely |
| Indicators | 1e-8 relative after warm-up | |

A tolerance is never widened to make a test pass. A real difference is either fixed in Studio or recorded in `DECISIONS.md` as an intended difference, with the reason and its own test.

## 5. Data honesty (the part LEAN can't fix)

LEAN gets its accuracy from raw prices plus factor files (splits, dividends) and map files (ticker changes). Our data is mixed raw and adjusted, with no dividend or split columns (`DECISIONS.md`). So:

- Parity tests prove **engine correctness on given prices**. They don't make our prices correct.
- Fixtures run in LEAN `Raw` mode with flat factor files, so both engines see the same series.
- Phase 9 (data refresh) adds raw OHLCV plus split and dividend events. Then Studio adopts LEAN's model: keep raw prices, apply factors at read time, and support the modes `Raw`, `Adjusted`, `SplitAdjusted` and `TotalReturn`. At that point the parity fixtures gain real factor files, and dividend cash and short dividend charges become testable.
- Survivorship: LEAN's US data includes delisted names; ours mostly doesn't (1.3%). The parity test can't catch this; the survivorship label stays.

## 6. Scope: every backend module

| Module | Parity target |
|---|---|
| `core/fills.py` | Fill, slippage and fee models per §3 rows 4–9 |
| `core/engine.py` (vector + event) | Rows 1–3, 9–14, 18; both engines against the same golden |
| `core/formula.py` | Row 19, indicator goldens |
| `core/backtest.py` | Row 15–16 stats, benchmark, trades table |
| `core/portfolio.py` | Combined equity of members equals a LEAN multi-strategy run with fixed weights and the same rebalance dates |
| `core/validate.py` | Walk-forward windows each equal a LEAN run on that window (start-date cut, warm-up respected); PSR, DSR from LEAN formulas |
| `core/optimise.py` | Each sweep cell equals a single LEAN run at those settings (sample of cells, not all) |
| `core/live.py` | Paper fills follow the same fill model as backtest; one test replays a backtest day through `live` and expects identical orders |
| `core/pyrunner.py` | A Python strategy written once runs in Studio's event engine and as a LEAN algorithm through a thin `ctx` shim; identical orders |
| `research_v2`, `factors_v2`, `ml_v2`, `pca_v2` (labs) | Out of LEAN's scope (no trading engine). Checked against reference libraries instead: statsmodels, linearmodels, scikit-learn, arch. Separate file, later |

## 7. Order of work

1. **Harness.** Fixtures, `to_lean.py`, one buy-and-hold algorithm, `lean backtest` in Docker, golden JSON, `parity.py`. Done when SPY buy-and-hold equity matches to the cent.
2. **Fills and timing** (rows 1–6, 12–14) with signal, stop, target, gap and delisting templates on both engines.
3. **Costs** (rows 7–9): constant, volume-share and market-impact slippage; IB fees; integer shares and cash buffer.
4. **Buying power and shorting** (rows 10–11).
5. **Statistics** (row 15) and benchmark: the full LEAN statistics block.
6. **Indicators** (row 19) from LEAN's test data.
7. **Portfolio, validate, optimise, live, Python runner** (§6).
8. **Data refresh link** (§5) when phase 9 lands.

Each step: tests first (they fail), then the fix, then `CODE_STANDARDS.md` gates, then commit. A step isn't done until both engines pass its goldens.

## 8. Risks

- **LEAN version drift.** Pin the Docker image tag; refresh goldens only deliberately, and review the diff.
- **Docker cost.** Goldens are cached, so normal test runs need no Docker. Only `--refresh-lean` does.
- **Speed.** Integer shares and buying-power checks enter the numba kernel; benchmark sweeps before and after, with a budget of no more than 10% slower.
- **Behaviour change for saved runs.** New fill semantics change old results. Bump the engine version in run metadata, and show "engine changed since this run" on older runs instead of silently recomputing them.
- **LEAN isn't ground truth for market reality.** It's a well-tested reference implementation. Where LEAN is optimistic (full fills, no partial fills on daily bars), Studio may be stricter, but only as a named option that parity tests turn off.

## 9. Licence

Ported code carries `# Ported from QuantConnect LEAN (Apache 2.0), <LEAN path>`. A NOTICE entry lists LEAN. No LEAN data files are committed beyond its market hours database and test CSVs, which are Apache 2.0 in the same repo.
