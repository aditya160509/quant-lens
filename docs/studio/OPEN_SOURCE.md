# Studio open-source licence register, November 2026

Checked 2026-11-15. Sources: GitHub repo API (`spdx_id`, `pushed_at`), raw LICENSE files, PyPI JSON, and vendor pages.

## Shipping rule

- **Ship OK:** MIT, BSD-2/3, Apache-2.0.
- **Separate process only:** LGPL-3.0. Never linked into server code.
- **Decide first:** MPL-2.0 (file-level copyleft). Not in the banned list, but the house rule says copyleft is ideas only, so it needs your OK.
- **Ideas only:** GPL, AGPL. Read for ideas, never copy code.
- **Never:** SSPL, Commons Clause, unlicensed.

"Maintained" = last GitHub push (`pushed_at`) or last PyPI release, whichever the source gives. Both are dates from today's checks.

## Register

| Project | What it does for us | Licence (SPDX) | Ship? | Maintained | Use as |
|---|---|---|---|---|---|
| vectorbt (open source, polakowo) | Vectorised backtests, parameter sweeps | Commons Clause (LICENSE.md title "Commons Clause License Condition v1.0"); base licence not confirmed | **No** (Commons Clause) | PyPI "vectorbt" 1.2.1, 2026-11-11, but its README links vectorbt.pro. That is the PRO package, not the open-source one. Repo API failed. | Reference only |
| nautilus_trader | Event-driven backtest and live engine | LGPL-3.0 (GitHub API) | Separate process only | Push 2026-10-04 | Reference, or separate process later |
| zipline-reloaded | Event backtester (Zipline fork) | Apache-2.0 (LICENSE read) | Yes | PyPI 3.2.1, 2026-10-25 | Reference; dependency if we need pipelines |
| backtesting.py (kernc) | Single-asset backtests, heatmap optimisation | AGPL-3.0 (GitHub API) | **No** | Push 2026-08-05 | Ideas only (heatmap, optimisation UI) |
| backtrader | Event backtester | GPL-3.0 (LICENSE read) | **No** | PyPI 1.9.78.123, 2023-04-19 (stale) | Ideas only |
| bt (pmorissette) | Portfolio-level backtests, tree of weights | MIT (GitHub API) | Yes | PyPI 1.4.1, 2026-10-10; push 2026-11-13 | Dependency or copy the idea |
| LEAN (QuantConnect) | Full engine, report generator | Apache-2.0 (GitHub API) | Yes (but heavy) | Push 2026-10-23 | Reference for report design; dependency only if we need LEAN's engine |
| freqtrade | Crypto bot, hyperopt, lookahead analysis | GPL-3.0 (LICENSE read) | **No** | Repo API failed; release date unverified | Ideas only (lookahead check) |
| jesse | Crypto backtest framework | MIT (LICENSE read) | Yes | Repo API failed; release date unverified | Copy the idea or dependency |
| quantstats | Tearsheet and metrics | Apache-2.0 (GitHub API) | Yes | PyPI 0.0.86, 2026-09-27 | Dependency or copy the metric list |
| pyfolio-reloaded | Tearsheets (returns, risk, positions) | Apache-2.0 (GitHub API) | Yes | PyPI 0.10.2, 2026-11-02 | Dependency |
| empyrical-reloaded | Metric functions (Sharpe, Sortino, drawdown, etc.) | Apache-2.0 (GitHub API) | Yes | PyPI 0.7.2, 2026-11-02; push 2026-11-08 | Dependency; test oracle |
| alphalens-reloaded | Factor tests (IC, quantiles) | Apache-2.0 (GitHub API) | Yes | PyPI 0.5.1, 2026-10-26 | Dependency; test oracle |
| riskfolio-lib | Portfolio optimisation, many risk measures | BSD-3-Clause (GitHub API) | Yes | Push 2026-11-04 | Dependency (if we need allocation) |
| skfolio | Portfolio optimisation, CPCV (`model_selection/_combinatorial.py`) | BSD-3-Clause (GitHub API, PyPI) | Yes | PyPI 1.12.16, 2026-11-14 | Dependency for CPCV; test oracle |
| PyPortfolioOpt | Mean-variance, HRP and related | MIT (PyPI, PyPortfolio repo) | Yes | PyPI 1.6.0, 2026-02-26; push 2026-07-07 | Dependency or reference |
| cvxpy | Convex solver front end | Apache-2.0 (GitHub API) | Yes | PyPI 1.9.3, 2026-09-19; push 2026-11-12 | Dependency |
| arch (bashtage) | GARCH, bootstrap, volatility models | NOASSERTION on GitHub; licence file not fetched (LICENSE.txt 404 on main) | **Unverified: do not ship until checked** | Push 2026-08-10 | Reference; check the LICENSE file first |
| optuna | Parameter search with pruning | MIT (GitHub API) | Yes | Push 2026-11-13 | Dependency for optimiser |
| pandas-ta | Indicator library | MIT (freqtrade fork LICENSE read); upstream repo not reachable | Yes, after checking upstream | PyPI 0.4.71b0, 2025-09-14 (stale) | Copy indicator formulas only, or skip |
| TA-Lib (python wrapper) | Indicators in C | BSD-2-Clause (GitHub API) | Yes (C library also BSD) | PyPI 0.8.3, 2026-10-28; push 2026-10-29 | Dependency for speed |
| polars | DataFrames | MIT (GitHub API, PyPI) | Yes | PyPI 2.1.0, 2026-10-25; push 2026-11-13 | Dependency |
| DuckDB (Python) | SQL over frames, window queries | MIT (LICENSE read) | Yes | Repo API failed; release date from screener reference 2026-10-21 (unverified here) | Dependency |
| duckdb-wasm | DuckDB in the browser | MIT (GitHub API) | Yes | Push 2026-11-13 | Dependency (browser) |
| Pyodide | Python in the browser (WASM) | MPL-2.0 (GitHub API) | **Decide first** (file-level copyleft) | Push 2026-11-14 | Reference unless you approve |
| Monaco editor | Code editor | MIT (LICENSE.txt read) | Yes | Repo API failed; `Editor.jsx` already uses it | Dependency (already in use) |
| lightweight-charts (TradingView) | Price charts, panes | Apache-2.0 (LICENSE read) | Yes | Repo API failed; installed v5.1 per screener reference | Dependency (already in use) |
| KLineChart | Charts with indicators and drawing tools (per README) | Apache-2.0 (GitHub API) | Yes | Push 2026-11-14 | Alternative chart; check drawing tools before adoption |
| FINOS Perspective | Large-table and pivot engine (WASM) | Apache-2.0 (GitHub API) | Yes | Push 2026-11-13; v5.8.0 per screener reference (unverified here) | Dependency for pivots, if needed |
| PineTS (LuxAlgo) | Runs Pine Script in JavaScript | AGPL-3.0 (GitHub API, LICENSE read) | **No** | Push 2026-11-13 | Ideas only (Pine semantics) |
| Pine transpilers (pynescript, pynesys, others) | Pine to Python | **Unverified** (licence not read) | **Unverified** | Unverified | Reference only until read |
| OpenBB Platform | Data platform | **Conflict:** repo LICENSE says Apache-2.0; the OpenBB blog says the main repo moved to AGPL | **Treat as AGPL until resolved** | Repo API failed | Reference only |

## Notes on conflicts and gaps

- **vectorbt:** the PyPI package named "vectorbt" 1.2.1 is the PRO package (README links vectorbt.pro). Do not depend on it for the open-source edition.
- **OpenBB:** the repo LICENSE and the blog disagree. Keep it as reference until a maintainer confirms.
- **arch:** GitHub lists NOASSERTION and the raw LICENSE.txt path returned 404. Find the real file before any use.
- **pandas-ta:** upstream repo returned 404 on twopirllc. The freqtrade fork's MIT licence is what was read.
- **Release dates:** the GitHub API failed for several repos (vectorbt, zipline, backtrader, freqtrade, jesse, DuckDB, Monaco, lightweight-charts, OpenBB). For those, dates come from PyPI, from the screener reference, or are marked unverified.

## Recommended stack

Built on the permissive libraries above. No copyleft code ships.

1. **Data frames and SQL:** polars (MIT) for frames; DuckDB (MIT) for SQL over the bars and trade logs. Browser DuckDB via duckdb-wasm (MIT) for offline views.
2. **Engine:** our own vectorised backtester on polars or NumPy. Borrow ideas from bt (MIT) for weight trees and from backtesting.py and freqtrade (ideas only) for heatmaps and lookahead checks. Do not depend on vectorbt or backtesting.py.
3. **Indicators:** TA-Lib (BSD-2) for speed. pandas-ta only for formula checks.
4. **Validation:** skfolio (BSD-3) for CPCV and as a test oracle; empyrical-reloaded and alphalens-reloaded (Apache-2.0) as test oracles for metrics and factor tests; our own walk-forward, Monte Carlo and regime code.
5. **Tearsheet:** pyfolio-reloaded and quantstats (Apache-2.0) as dependencies or a copied metric list. LEAN (Apache-2.0) report design as a reference.
6. **Optimiser:** optuna (MIT) with pruning.
7. **Allocation (if needed):** riskfolio-lib (BSD-3) or PyPortfolioOpt (MIT); cvxpy (Apache-2.0) as the solver front end.
8. **Charts:** lightweight-charts (Apache-2.0, already installed). KLineChart (Apache-2.0) only if its drawing tools meet the spec.
9. **Code editor:** Monaco (MIT, already in use). Pine: write our own parser. PineTS is AGPL, so ideas only.
10. **Browser Python:** Pyodide is MPL-2.0. Decide before using it. Default: no.
11. **Open decisions for you:** Pyodide (MPL-2.0), OpenBB (licence conflict), arch (licence file missing), any Pine transpiler (not read).
