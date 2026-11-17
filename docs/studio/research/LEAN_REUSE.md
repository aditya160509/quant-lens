# What Studio takes from LEAN

LEAN (QuantConnect's engine) is Apache 2.0: github.com/QuantConnect/Lean. We may port its formulas into Python. Any file that ports LEAN code keeps a header line: `# Ported from QuantConnect LEAN (Apache 2.0), <path in LEAN>`. Their web IDE and results page are not open source; only layout ideas are taken from those (`UI_CANON.md` §12).

We port formulas, not the engine. LEAN is C#, minute- and tick-based, and needs its own data format; Studio is daily, numba-vectorised and has its own event engine.

Read from LEAN master on 2026-11-17.

## Port: fills and costs (`core/fills.py`)

Studio today has one cost model: flat bps slippage plus a share of the bar range, and commission = max(min, bps + per-share).

| LEAN model | Formula | Defaults | Use in Studio |
|---|---|---|---|
| `VolumeShareSlippageModel` (Common/Orders/Slippage) | share = min(qty / bar volume, limit); slip % = share² × impact; slip = slip % × price | limit 0.025, impact 0.1 | New slippage option "volume share". Daily volume exists for every ticker; slippage grows with order size, so capacity tests become honest |
| `MarketImpactSlippageModel` (Almgren-Chriss) | ν = qty / exec time / avg volume; permanent = σ·T·γ·ν^α; temporary = σ·η·ν^β; realised = temporary + ½ permanent; capped at 100% | latency 0.075 s, impact time 1800 s, α 0.891, β 0.600, γ 0.314, η 0.142, δ 0.267 | "Market impact" option for large books; σ from 20-day returns. Drop LEAN's random noise term so runs stay reproducible |
| `InteractiveBrokersFeeModel`, US equity | fee = 0.005 × shares; below $1 → min($1, 1% of trade value) | $0.005/share, $1 min, 1% cap | Named cost profile "IB US fixed" in Library |
| Same, India | 0.01 INR/share, min 6 INR | | Hold until India coverage is measured (`DECISIONS.md`) |
| Same, forex | 0.20 bp of value, $2 min (tiered by monthly volume) | | Not needed: Studio is equities |

## Port: statistics (`core/backtest.py`, `core/validate.py`)

LEAN files: `Common/Statistics/Statistics.cs`, `PortfolioStatistics.cs`.

| Stat | LEAN formula | Studio today | Action |
|---|---|---|---|
| Probabilistic Sharpe ratio | (SR − SR*) / √((1 − skew·SR + (kurt − 1)/4 · SR²) / (n − 1)), on daily returns; LEAN's SR* = 1/√252 (annual Sharpe of 1) | `M.psr` exists in validate | Check our denominator matches (LEAN uses kurtosis, not excess kurtosis), and show PSR in the Backtest stat strip as QuantConnect does |
| Expectancy | win rate × (avg win / \|avg loss\|) − loss rate | Missing | Add to trade stats |
| Profit-loss ratio | avg win % / \|avg loss %\|, each trade's P&L divided by running capital | Missing | Add |
| Average win / loss rate | per-trade P&L ÷ capital at that time | Partial | Align with LEAN's running-capital basis |
| Alpha, beta | β = cov(r, b) / var(b); α = annual return − (rf + β(annual bench − rf)) | beta exists | Add Jensen alpha beside beta |
| Tracking error, information ratio | √(annual var of r − b); IR = mean(r − b) / std(r − b) annualised | Missing | Add to benchmark row |
| Treynor | (annual return − rf) / β | Missing | Add |
| Sortino | annual (mean − MAR) / annual downside std | In optimise only | Share one function |
| Drawdown recovery | max days from peak to recovered peak | Episodes table has recovery dates | Add "longest recovery (days)" to stat strip |
| Value at risk 95/99 | parametric (normal) on daily returns | Missing | Add both, labelled "normal approximation" |
| CAGR | (final / start)^(1/years) − 1, years = days/365 | Exists | Same |

## Port: the backtest result layout

QuantConnect's results page order: headline stat strip (equity, fees, net profit, PSR, return, unrealised, volume, capacity), then equity chart with ranges and daily-return bars, then chart picker, then tabs (overview, orders, trades, insights, logs, report). Studio's Backtest page already follows this. Add the fields it lacks: **fees total**, **PSR** and **volume traded**.

## Port: LEAN Report (`Report/`)

LEAN's report generator makes a PDF and HTML tear sheet: rolling Sharpe and beta, returns per month heatmap, crisis events, exposure, drawdown periods, and leverage. Studio has most of these as views. Take the **crisis event list with exact date ranges** (Report/ReportElements/CrisisReportElement and `Common/Statistics/...Crisis`), filtered to 2015+ per `DECISIONS.md`: 2015 August flash crash, 2018 Q4, 2020 Covid crash, 2020 recovery, 2022 rates.

## Don't port

| LEAN part | Why not |
|---|---|
| Engine, scheduling, universe selection | Studio has its own engine with parity tests; LEAN needs its own data format |
| Brokerage adapters, live trading | Live stays paper until data refresh (phase 9) |
| Minute and tick fill models (`ImmediateFillModel` intra-bar logic) | Studio is daily only (hourly removed 2026-11-16) |
| Options, futures, crypto, forex margin models | Equities only |
| Alpha framework (Insights, PCM, execution model) | Studio rules already cover signal → weight → order |

## Order of work

1. Volume-share slippage plus "IB US fixed" fees (small, raises capacity honesty).
2. Expectancy, P/L ratio, alpha, information ratio, Treynor, VaR, longest recovery, fees total, volume.
3. Check PSR formula against LEAN; put PSR in the stat strip.
4. Market-impact slippage (no random term).
5. Crisis dates table (2015+).

Each step adds parity tests in `tests/test_studio_v3_*.py` against numbers computed by hand from the LEAN formula.
