# Screener V2 — Full Spec Compliance Audit

## Remediation checklist (2026-07-13)

- [x] Removed the unreferenced 3,025-line `core/screener_v2_combined.py` duplicate after import/reference verification.
- [x] Added `/api/screener-v2/features`, `/api/screener-v2/run/{feature_id}`, and CSV-upload routes.
- [x] Corrected overnight gap to `(open_t - close_{t-1}) / close_{t-1}`.
- [x] Deduct transaction costs on rebalance dates instead of smearing them over every observation.
- [x] Added general after-tax ROIC using invested capital.
- [x] Confirmed raw `if(...)` formulas are translated safely to `where(...)` before AST evaluation.
- [x] Added industry-group, negative-P/E, ROIC, Bollinger-width, and PROX52-percentile filters.
- [x] Added selectable heatmap metrics and market-cap sizing.
- [x] Added full CSV, TSV, JSON, and plain-ticker export payloads.
- [x] Added a real streaming CSV download endpoint and made CSV the default export format.
- [x] Hardened JSON serialization for NumPy booleans, timedeltas, and complex values.
- [x] Added configurable RSI, stochastic, ADX, ATR, Bollinger, and MACD parameters.
- [x] Fixed user-selected N-day golden/death-cross filtering using actual event age.
- [x] Replaced the EWMA volatility proxy with a vectorized Yang-Zhang range estimator scaled to 21 days.
- [x] Added historical formula evaluation that truncates prices and reported fundamentals at `as_of_date`.
- [x] Added explicit formula division/log guards and deterministic validation for time-operator arguments.
- [x] Expanded the formula library with Piotroski-, Altman-, Magic Formula-, QMJ-, ERP5-, shareholder-yield-, and Graham-style templates.
- [x] Expanded factor-zoo IC comparison across available signals and return horizons.
- [x] Added explicit percentile, z-score, and signed-rank composite output scales.
- [x] Corrected Magic Formula, Graham Net-Net, Dogs-of-the-Dow-style large-cap selection, Altman missing-data handling, and Altman thresholds.
- [x] Fixed holding-period sensitivity to measure independent forward holding returns without re-fetching prices.
- [x] Added weekly/monthly/quarterly rebalance-frequency aliases.
- [x] Removed the duplicate/ad-hoc volume alert and corrected the fundamental-change strict threshold.
- [x] Corrected FCF-yield direction in peer, universe, and sector valuation percentiles.
- [x] Added P/S to the ranked table and corrected CSV defaults/order handling.
- [x] Added focused regression tests for gap math, formula guards, holding horizons, and rebalance-cost timing.
- [ ] Requires external data: true point-in-time fundamentals, delisted-security history, and index membership histories.
- [ ] Requires infrastructure: durable saved screens, alert state, email delivery, scheduler, and prior-run comparison storage.
- [ ] Intentionally deferred as disproportionate compute: full-universe nested purged CV and Monte Carlo optimization on every interactive request; these belong in offline cached jobs.
- [ ] Intentionally deferred as a non-functional refactor: splitting `analytics.py` into many modules. The duplicate was removed; a large file alone is not a mathematical or runtime defect.

---

---

## 1. Lines of Code Summary

| Component | Files | Lines |
|---|---|---|
| Core analytics | `core/analytics.py` | 2,254 |
| Core data loader | `core/data_loader.py` | 240 |
| Core GICS | `core/gics.py` | 77 |
| Core performance | `core/performance.py` | 179 |
| Core combined | `core/screener_v2_combined.py` | 3,025 **(duplicate of above 4 files)** |
| Feature 01 | `features/feature_01.py` | 108 |
| Feature 02 | `features/feature_02.py` | 66 |
| Feature 03 | `features/feature_03.py` | 94 |
| Feature 04 | `features/feature_04.py` | 71 |
| Feature 05 | `features/feature_05.py` | 138 |
| Feature 06 | `features/feature_06.py` | 84 |
| Feature 07 | `features/feature_07.py` | 46 |
| Feature 08 | `features/feature_08.py` | 46 |
| Registry | `registry.py` | 65 |
| Fetchers | `fetchers/fetch_missing_data.py` | 101 |
| Package init | `__init__.py` + `features/__init__.py` | 6 |
| **Total unique** | **17 files** | **3,575 lines** |
| **With duplicate** | **18 files** | **6,600 lines** |

The `screener_v2_combined.py` (3,025 lines) is an exact duplication of `data_loader.py` + `gics.py` + `performance.py` + `analytics.py` concatenated with minor node ordering differences (e.g., `_last_sign_cross_age` and `_trailing_true_count` are not inlined, but the combined version also drops PIT fundamental formula support that exists in the standalone `analytics.py`). This duplication is a maintenance hazard — the standalone files are the live ones; the combined file appears to be a stale snapshot.

---

## 2. Per-Feature Audit (F01–F08)

### F01 — Core Multi-Factor Screener Engine (feature_01.py: 108 lines)

**Spec targets (features.md + computation.md):**
- Universe selection: all 5,000 tickers, S&P 500/400/600, Russell 1000, custom CSV upload, GICS sector/industry group
- Descriptive filters: market cap (slider + presets), GICS sector/industry/industry-group, exchange, price range, dollar volume, shares outstanding, float %
- Technical filters: SMA/EMA crossovers, MACD, Bollinger Bands, ATR, ADX/DMI, beta, stochastic, Williams %R, OBV slope, volume ratio, gap, consecutive days, RSI, short-term reversal, relative performance vs SPY
- Fundamental filters: P/E, fwd P/E, P/B, P/S, P/CF, EV/EBITDA, EV/Sales, EV/EBIT, Earnings Yield, gross/operating/net/EBITDA margins, ROE, ROA, ROIC, GP/A, revenue/earnings growth YoY, revenue 3Y CAGR, D/E, Debt/EBITDA, current/quick ratios, interest coverage, OCF/NI, dividend yield, payout ratio
- Platform signals: composite score, vol forecast, Amihud, MAX factor, IVOL, 52-week proximity
- Three simultaneous percentiles: universe, GICS sector, GICS industry group
- Filter funnel waterfall, heatmap, quick-look card, saved screens

**Implemented:**
- Universe: `parse_symbols()` handles master/SP500 aliases, ticker lists; custom CSV upload is not implemented as a file endpoint but ticker strings work
- Descriptive: market_cap, sector, exchange, price, dollar_volume, shares_outstanding, float_percent filters all present
- Technical: RSI, MACD, Bollinger, ATR, ADX, DMI, beta, stochastic, Williams %R, OBV, vratio, gap, consecutive days, SMA/EMA distances all computed in `latest_technical_features()`
- Fundamental: computed in `latest_fundamental_features()` — 33+ metrics including all listed in spec
- Platform signals: vol_forecast_21d, amihud_percentile, ivol_ff3_63d, max_1d_return_21d, prox52
- Percentiles: universe, sector, industry_group, industry relative percentiles computed for 5 primary score components
- Filter funnel waterfall: `apply_filters()` tracks stages
- Heatmap: `heatmap_view()` groups by sector
- Quick-look card: `quick_look()` returns chart_full, chart_windows

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **No Russell 1000 proxy** | `parse_symbols()` knows "sp500" but not Russell 1000, S&P 400, or S&P 600 aliases |
| 2 | **No custom CSV upload** | No file upload endpoint — listed in spec as input |
| 3 | **No GICS industry-group filter in F01** | The industry_group tier is computed in analytics.py but F01 does not expose an industry_group filter payload key (only sector and industry) |
| 4 | **No SMA crossover filter by user-specified N days** | `apply_filters` has `golden_cross_within_n_days` and `death_cross_within_n_days` but only checks the hardcoded 20-day window from the golden_cross_within_20d / death_cross_within_20d column. User cannot set "golden cross within 5 days" or "within 60 days" |
| 5 | **No user-settable RSI period** | RSI is hardcoded at 14 |
| 6 | **No stochastic period parameters** | Hardcoded K=14, D=3 |
| 7 | **No ADX period parameter** | Hardcoded at 14 |
| 8 | **No user-set Bollinger Band std multiplier** | Hardcoded at 2 |
| 9 | **No MACD fast/slow/signal period parameters** | Hardcoded 12/26/9 |
| 10 | **No ATR period parameter** | Hardcoded at 14 |
| 11 | **Heatmap does not render by market cap size** | `heatmap_view()` returns sector aggregates as flat list; the spec says "Size = market cap. Color = metric" — the size encoding is missing |
| 12 | **No saved screens persistence** | F01 emits empty `saved_screens: []` — acknowledged in README |
| 13 | **No scheduled re-run / change notifications** | Not implemented |
| 14 | **No 52-week high proximity filter as continuous percentile** | `prox52` filter exists as min/max but the spec calls for "cross-sectional percentile; filter to top/bottom decile" |
| 15 | **ROIC approximation missing** | Spec says `ROIC = EBIT(1-t) / (Total Equity + Total Debt − Cash)`. The implemented analytics.py does compute `roa_calc` and `roe` but does NOT compute spec-compliant ROIC. The `greenblatt_roic()` function in analytics.py computes a different formula: `EBIT / (NetWorkingCapital + NetFixedAssets)` — this is the Greenblatt-specific ROIC, not the general ROIC |
| 16 | **P/E negative exclusion and sector-relative percentile** | Spec says "negative P/E exclusion toggle" and "sector-relative percentile" for P/E. Sector-relative percentile exists for the score components but not for raw P/E |
| 17 | **Bollinger band width percentile** | Present as `bollinger_width_percentile` but not filterable |
| 18 | **Sector heatmap — color by any metric** | Spec says "any user-selected metric". Implementation hardcodes `core_quant_score` as the metric with no parameter to select others |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | `latest_technical_features()` line 258: `out["gap_1d"] = prices.iloc[-1] / prices.iloc[-2] - 1.0` — this is daily close return, not gap. The gap spec requires `(O_t - C_{t-1}) / C_{t-1}` (open vs prior close). This uses close vs prior close, which is wrong. | analytics.py:341 |
| 2 | `vol_forecast_21d` is computed as EWMA vol × sqrt(21), not the Yang-Zhang HAR forecast from the Vol module as the spec requires | analytics.py:373 |
| 3 | `market_cap_bucket_distribution` uses `pd.qcut` which fails when all market caps are identical | feature_01.py:47-48 |
| 4 | Float percentage filter (`float_percent`) uses raw value not restricted-float flag per spec (float < 5% flag) | analytics.py:688 |
| 5 | Consecutive days formula `_trailing_true_count` counts consecutive True values but the spec says "CONSEC_{i,t} = CONSEC_{i,t-1} + 1 if sign(R_{i,t}) = sign(R_{i,t-1})" — this counts consecutive up days correctly but the implementation only checks that returns are > 0, not that consecutive sign matches. If a day has 0 return, the chain breaks, which is correct per spec. | analytics.py:409-415 |
| 6 | The F01 runner does not expose the `ps_ratio` column in the output table. P/S is computed in fundamentals but not added to `top_table()` columns. | feature_01.py:728-773 |
| 7 | The `ranking` key in cross-sectional percentile context does not include the per-metric sector/industry group percentiles (just the 5 score components). The spec says "Every metric in the table shown alongside its percentile rank in (a) full 5,000-ticker universe, (b) GICS sector, (c) GICS industry group." | feature_01.py:52-76 |

**Score: 5/10**

---

### F02 — Formula Builder (feature_02.py: 66 lines)

**Spec targets:**
- Expression parser with `+`, `-`, `*`, `/`, `^`, `sqrt()`, `abs()`, `log()`, `min()`, `max()`, `if()`
- Time operators: `lag(field,N)`, `rolling_mean/std/max/min`
- Cross-sectional operators: `rank()`, `sector_rank()`, `zscore()`, `sector_zscore()`
- Full field registry with OHLCV, returns, fundamentals, FF factors, platform signals
- Historical evaluation date picker
- Pre-built template library (Piotroski, Altman Z, Magic Formula, etc.)
- Walk-forward formula backtest with IC computation, ICIR, purged cross-validation
- Factor zoo comparison

**Implemented:**
- `FormulaEngine` class with AST-based parsing using `ast.parse()`
- Operators: `+`, `-`, `*`, `/`, `^` (via `**` replacement), `abs`, `log`, `sqrt`, `min`, `max`, `rank`, `zscore`, `sector_rank`, `sector_zscore`, `where` (as `if`)
- Time operators: `lag`, `rolling_mean`, `rolling_std`, `rolling_max`, `rolling_min` with true local history for price/OHLC fields and PIT fundamental fields
- Field registry includes most spec fields via panel columns
- `formula_templates()` returns 5 templates
- `score_backtest()` provides long-only backtest with stats
- Factor zoo comparison computes Spearman IC vs 1-month return

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **No `if(condition, val_true, val_false)` in formula syntax** | The spec uses `if(...)`. Implementation substitutes `if(` -> `where(`. This is reasonable but means raw spec formulas like `if(roa > 0, 1, 0)` won't work without pre-processing |
| 2 | **No true historical date picker** | Formula evaluation runs at the current date only. Spec requires "run the formula on any historical date via date picker" |
| 3 | **Template library is incomplete** | Only 5 templates. Spec lists 15+ including Piotroski F-Score, Altman Z, Greenblatt Magic Formula, O'Shaughnessy Trending Value, Conservative Formula, QMJ, Acquirer's Multiple, Shareholder Yield, ERP5 |
| 4 | **No walk-forward backtest with ICIR** | `score_backtest()` returns basic stats (Sharpe, drawdown) but not IC_k series, ICIR, purged cross-validation, or the full walk-forward spec |
| 5 | **Factor zoo comparison limited** | Only compares against return_1m; spec calls for IC ranked against every other platform signal |
| 6 | **no `log()` on scalar** | `math.log()` is called but `number_like()` may not handle all cases. The implementation `_call("log")` uses `np.log` for series but `math.log` for scalars — the branch on `isinstance(args[0], pd.Series)` is fragile |
| 7 | **FF factor fields not in panel** | FF factors are added via `metric_panel` but only as a single row (latest date) — they have no time series in the formula context |
| 8 | **Formula reference list incomplete** | Spec lists `open`, `high`, `low`, `close`, `adj_close`, `volume` as available field names. The panel includes `close`, `price`, `open`, `high`, `low`, `volume_today`, `volume_20d` but not `adj_close` or raw `volume` |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | `FormulaEngine` only supports `node.args[0].id` for time-series field name extraction — fails if the first argument is a complex expression, not a simple field name | analytics.py:928 |
| 2 | `node.args[1].value` assumes the second argument is a `Constant` — crashes if user writes `lag(close, n)` where `n` is a computed expression | analytics.py:932 |
| 3 | `_field_time_matrix` in analytics.py does NOT include the full return horizon mapping that the standalone analytics.py has (the `RETURN_HORIZON_FIELDS` dict). The combined file's version only supports `price`, `close`, `adj_close`, `open`, `high`, `low`, and `return_1d`. | combined.py:1394-1395 vs analytics.py:974-988 |
| 4 | No division-by-zero guard — division by zero returns inf/nan, which gets filled with 0 at the end, but the spec requires explicit guard signaling | analytics.py:896 |
| 5 | `rolling_std` with `min_periods=2` may produce NaN when `min_periods=1` would be more permissive | combined.py:1422 |

**Score: 4/10**

---

### F03 — Composite Quant Score Engine (feature_03.py: 94 lines)

**Spec targets:**
- Factor components from all platform signals, up to 50
- Weighting modes: equal, IC-IR-weighted (Grinold-Kahn), manual, ridge-regularized OLS
- IC-IR estimation window: rolling 63/126/252 days or expanding
- Sign convention auto-correction for valuation/vol/distress factors
- Sector and beta neutralization
- Winsorization at 1st/99th percentile then z-score
- Output scales: 0-100 percentile, -3 to +3 z-score, [-1,+1] signed rank
- Preset composite strategies (7 listed)
- Score transparency decomposition (waterfall chart)
- Component IC-IR leaderboard
- Factor correlation heatmap with redundancy alerts (>0.6)
- Effective number of independent factors
- Regime-conditional IC decomposition
- Composite vs individual factor backtest

**Implemented:**
- Component selection with manual/IC-IR/ridge weighting
- Sign auto-correction via `sign_correct()` with VALUATION_FIELDS, VOLATILITY_FIELDS, DISTRESS_FIELDS_INVERTED sets
- Sector neutralization (subtract sector median)
- Beta neutralization (OLS slope subtraction)
- Winsorization at 1st/99th percentile
- Signed rank [-1,+1] output
- Preset strategies: aqr_quality_value, momentum_quality, low_vol_quality, vmq, ff5_screen, conservative_formula, trending_value
- Score decomposition via `score_decomposition_for_ticker()`
- IC-IR bootstrap leaderboard via `component_ic_leaderboard()`
- Correlation heatmap via `matrix_records(corr)`
- Effective number of factors via `effective_num_factors()`
- Redundancy alerts for pairs > 0.6 correlation
- Composite vs factor backtest via `score_backtest()`

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **IC-IR weighting is bootstrap-cross-sectional, not walk-forward** | The spec requires weight ∝ Spearman IC / IC std from rolling 252-day walk-forward history. Implementation uses bootstrap samples of the *current* cross-section. This is a proxy, not the true IC-IR. documented in diagnostics |
| 2 | **Ridge-regularized OLS is current-cross-section, not walk-forward** | Fits ridge on current cross-section and warns it is not a walk-forward fit |
| 3 | **No IC-IR estimation window toggle** | The bootstrap `n_boot` is hardcoded at 16, no parameter for 63/126/252/expanding |
| 4 | **Regime-conditional breakdown is a sector-grouping proxy, not VIX/yield-curve regime** | `regime_conditional_composite_breakdown` is `panel.groupby("sector")` — the spec calls for market regime (high vol, low vol, trending) |
| 5 | **No FA factor sign correction for accruals/distress** | `DISTRESS_FIELDS_INVERTED` is used only in `sign_correct()` of the standalone analytics.py but the set is small and doesn't include ALTMAN_Z, MAX_FACTOR as spec requires |
| 6 | **Preset strategies use percentiles not raw z-scores** | The spec says "z-score normalized factor signals"; implementation uses `valuation_percentile`, `quality_percentile` which are already rank-based (0-100), not z-scores |
| 7 | **No output scale 0-100 percentile option for the composite** | The composite score is a weighted average of percentile ranks (0-100), so it's already 0-100, but no explicit 0-100 vs z-score vs [-1,+1] parameter is exposed in the payload |
| 8 | **Effective number of factors formula differs from spec** | Implementation: `N_eff = (sum(w)^2 / sum(w^2)) / (1 + avg_rho)`. Spec: same formula. Correct. But the spec adds "closer to J means factors are independent" — weighted by w^2. Implementation is spec-compliant here |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | `component_scores()` builds the decomposition attrs on the output DataFrame but then `score_decomposition_for_ticker()` reads from `scored.attrs` — this is fragile because pandas DataFrame attrs are not preserved across many operations | analytics.py:1185-1188 |
| 2 | Weight negative handling: if `weight < 0` in the components list, the code flips `values = -values` and then takes `weight = abs(weight)`. But the sign_correct function may have already inverted the field. Double inversion possible | analytics.py:1166-1169 |
| 3 | `ff5_screen` preset includes negative weights for "Investment" and "Size" but these aren't z-score fields — `debt_assets` is a raw ratio, not a normalized factor | analytics.py:1113 |
| 4 | IC-IR leaderboard uses `n_boot=16` bootstrap draws — this is very small for statistical reliability | analytics.py:1198 |
| 5 | The leaderboard bootstrap in `component_ic_leaderboard` reuses the same `boot_indices` for all fields, which correctly samples the same observations for fair comparison. But target is the current cross-section 1-month return, not a forward return — this is not predictive IC | analytics.py:1198-1199 |

**Score: 5/10**

---

### F04 — Academic Strategy Screener Library (feature_04.py: 71 lines)

**Spec targets:**
- Pre-computation of all major academic formulas for all 5,000 tickers daily
- Full library: Greenblatt Magic Formula, Acquirer's Multiple, O'Shaughnessy Value Composite Two, ERP5, Deep Value Yield, Piotroski F-Score, Novy-Marx GPA, Mohanram G-Score, Sloan Accruals, Jegadeesh-Titman Momentum, Dual Momentum, Twin Momentum, Quantitative Momentum, Trending Value, Conservative Formula, QMJ, Meb Faber Shareholder Yield, Dogs of the Dow, High Dividend Low Payout, Altman Z/Z'', Interest Coverage Distress, Graham Net-Net, Altman Z+Piotroski overlay
- Strategy leaderboard with avg_score, coverage
- Per-strategy stock list
- Piotroski individual criterion scorecard (9 criteria)
- Altman Z-Score status with 8-quarter trend
- Strategy correlation matrix
- Historical strategy performance table (annualized return, Sharpe, MDD by strategy)
- Regime-conditional performance

**Implemented:**
- 22+ strategies in `academic_strategy_scores()`:
  - magic_formula, acquirers_multiple, value_composite_two, erp5_proxy, deep_value_yield, novy_marx_gpa
  - momentum_jt, low_vol, dual_momentum, twin_momentum, quantitative_momentum
  - quality_minus_junk (from qmj_composite), qmj_profitability/growth/safety/payout
  - net_payout_yield_spec, shareholder_yield_proxy, meb_faber_shareholder_yield
  - conservative_formula, trending_value, sloan_accruals, mohanram_g_score_proxy
  - graham_net_net, high_dividend_low_payout, dogs_of_dow_proxy, interest_coverage_distress
  - piotroski_f_score (spec + proxy), altman_z_score, altman_z_double_prime
- Strategy leaderboard via `strategy_leaderboard()`
- Piotroski scorecard via `piotroski_criteria()` and `piotroski_criteria_spec()`
- Altman Z 8-quarter trend via `altman_history()`
- Correlation matrix via `matrix_records(numeric.corr())`
- Full strategy performance table via `full_strategy_performance_table()`
- Historical strategy performance metadata

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **Acquirer's Multiple uses EV/EBIT when available but EV/EBITDA as fallback** | Spec says "EV/EBIT". Fallback to EV/EBITDA is reasonable given data constraints |
| 2 | **QMJ implementation in combined.py is a proxy** | The standalone analytics.py has a full `qmj_composite()` function with profitability, growth, safety, payout blocks. The combined.py file does NOT have this — it uses `quality_minus_junk_proxy = panel["quality_percentile"]`, which is a drastic simplification |
| 3 | **Quantitative Momentum in combined.py is a proxy** | Standalone analytics.py uses `momentum_smoothness()` from true local price history; combined.py has `quantitative_momentum = momentum_jt * inverse_vol_rank / 100` which is wrong — the spec says "rank(JT) + rank(MOM_SMOOTH)" |
| 4 | **Dual Momentum in combined.py** does not subtract risk-free rate; standalone analytics.py has `rf_trailing_252` subtraction but combined.py uses `> 0` only | combined.py:1653 vs analytics.py:1376-1380 |
| 5 | **Bollinger Band width percentile not filterable** | present in panel but not exposed in `apply_filters` |
| 6 | **No Graham Net-Net proper implementation** | Implementation checks `working_capital_assets > 0` and `pb_ratio < 1` but the formula is `current_assets - total_liabilities > market_cap`. Working capital is current_assets - current_liabilities, not current_assets - total_liabilities |
| 7 | **Dogs of the Dow proxy is a placeholder** | `np.where(sector == "Industrials", ...)` — the spec calls for "highest yield stocks in the large-cap universe", not a sector match |
| 8 | **Mohanram G-Score is a proxy** | Uses 6 generic factors; the spec has 8 specific growth/quality signals for high P/B growth stocks |
| 9 | **ERP5 is a proxy** | Combined EY rank + ROIC rank + 5Y avg EY + 5Y avg ROIC. The 5Y averages use 20 data points from fundamental_history (which is ~5 years of quarterly data), but this is an approximation without true PIT |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | `academic_strategy_scores` in combined.py raises `ValueError` on duplicate tickers (correct) but `full_strategy_performance_table` may re-duplicate via `set_index("ticker")` without handling duplicates | combined.py:1929 |
| 2 | `greenblatt_roic()` iterates over symbols in a Python for-loop — O(N) per ticker; on 5,000 tickers this is slow | analytics.py:1282-1304 |
| 3 | `piotroski_criteria_spec()` also iterates per ticker — same scalability concern | analytics.py:1462-1529 |
| 4 | Altman Z in `altman_z_score()` fills NaN components with 0 — this produces inflated scores (over 5) for tickers with missing balance sheet data instead of NaN | analytics.py:1562-1569 |
| 5 | `altman_status` uses `pd.cut` with bins `[-inf, 1.8, 3.0, inf]` — the spec says Z > 2.99 (safe), 1.81-2.99 (grey), < 1.81 (distress). The implementation uses 1.8 instead of 1.81 and 3.0 instead of 2.99. Small discrepancy but incorrect | analytics.py:1449 |
| 6 | `full_strategy_performance_table` calls `score_backtest` for each strategy in sequence — very slow for 24+ strategies without caching | analytics.py:1931-1936 |

**Score: 5/10**

---

### F05 — Screener Backtester (feature_05.py: 138 lines)

**Spec targets:**
- Walk-forward portfolio simulation with point-in-time data
- Survivorship bias correction (include delisted tickers)
- Portfolio construction: long-only top N, long-short top/bottom decile, score-weighted
- Rebalancing frequency: weekly/monthly/quarterly/semi-annual/annual
- Holding period: 1/5/21/63/126/252 days
- Transaction cost model: 0-50 bps
- Benchmark: SPY/equal-weight/market-cap-weight
- Sector neutralization
- Monte Carlo simulation with PBO
- Full statistics: CAGR, Sharpe, Sortino, Calmar, MDD, hit rate, avg gain/loss, info ratio
- Rolling performance (12m, 36m Sharpe)
- Holding period sensitivity
- Rebalancing date sensitivity
- Turnover report
- Sector attribution
- Stock-level attribution with entry/exit dates

**Implemented:**
- `score_backtest()` with long_only, long_short, score_weighted, sector_neutral
- Full stats: total_return, annualized_return/vol, sharpe, sortino, calmar, max_drawdown, avg_drawdown, hit_rate, average_gain/loss, best/worst calendar year, information ratio
- Rolling 63-day return/vol/sharp
- Holding period sensitivity via loop over [21, 63, 126, 252]
- Rebalancing date sensitivity via `rebalance_offset_days`
- Rebalancing date sensitivity by weekday via `score_backtest_by_weekday()`
- Turnover via `compute_turnover_series()`
- Sector attribution from selected tickers
- Monte Carlo `monte_carlo_pbo()` with rebalancing offset randomization
- PBO proxy via bootstrap Sharpe distribution
- Stock-level attribution with entry/exit dates (using returns index range)

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **No true point-in-time fundamental enforcement** | The data used is the latest fundamentals snapshot, not point-in-time by filing date. The meta warns about this |
| 2 | **No survivorship bias correction** | Uses currently-listed tickers only. Delisted tickers not included. Meta warns |
| 3 | **Holding period sensitivity calls `score_backtest` separately per horizon** | Each call re-fetches and recomputes the same price matrix — wasteful but not incorrect |
| 4 | **No Monte Carlo proper rebalancing-date randomization** | `monte_carlo_pbo()` randomizes rebalancing offset (0-20 days), not a full date permutation as the spec requires |
| 5 | **PBO proxy vs spec PBO** | Implementation computes beat_fraction vs benchmark Sharpe, but the spec has a proper Monte Carlo test with S trials at fully permuted dates |
| 6 | **No sector-neutral rebalancing as a dynamic portfolio engine** | `sector_neutral` divides selected tickers into sector legs and averages them — this is static sector allocation, not dynamic neutralization |
| 7 | **No weekly/monthly/quarterly frequency toggle** | The `rebalance_days` parameter accepts any integer, but the spec lists specific frequency options (weekly=5, monthly=21, quarterly=63). The implementation uses `rebalance_days` for cost calculation and turnover series but not for actual rebalancing simulation |
| 8 | **Holding period sensitivity `rebalance_days` parameter is not actually varied** | The loop passes `rebalance_days=hold` which changes the rebalance frequency, not the holding period. The spec requires testing holding periods independently |
| 9 | **Turnover report uses rank drift — not actual positions** | The spec requires turnover based on actual position changes between rebalancing periods. Implementation blends current scores with realized momentum to estimate rank drift |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | The `returns` variable in `score_backtest()` is initialized once but the function mutates returns via `returns.iloc[int(rebalance_offset_days):]` — if `rebalance_offset_days > 0`, the stat computation for the non-offset loop in the holding sensitivity section will use shifted returns | feature_05.py:70 |
| 2 | Transaction cost model: `daily = daily - (cost * rebalance_count / len(daily))` — this spreads the total cost evenly across every day, which is incorrect. Transaction costs should only be deducted on rebalancing days | analytics.py:1660-1661 |
| 3 | Monte Carlo PBO's `benchmark_sharpe` is computed against SPY, but the backtest uses equal-weight universe as benchmark. Comparing backtest Sharpe to buy-and-hold SPY Sharpe is not apples-to-apples | analytics.py:1991-1997 |
| 4 | `eligible_at_date()` checks if the first date of the price matrix index is valid, but the backtest may run across multiple rebalancing points — eligibility should be checked at each date | analytics.py:1629 |
| 5 | Stock-level attribution uses a single entry/exit date for all tickers (the min/max of the returns index) rather than per-position dates | analytics.py:2084-2087 |

**Score: 4/10**

---

### F06 — Alert Engine (feature_06.py: 84 lines)

**Spec targets:**
- Alert sources: any saved screen, formula, composite score, watchlist
- Trigger types: screen membership change, metric threshold, formula value threshold, composite score threshold, percentile rank shift, volume spike, price vs technical level, consecutive day trigger, fundamental change
- Alert frequency: daily/weekly
- Notification channels: in-platform panel, email
- Alert history log with forward performance tracking (1/5/21 days)
- Alert performance tracker: hit rate per alert type
- Screen entry/exit log
- Watchlist monitor dashboard

**Implemented:**
- Metric threshold alerts via `metric_threshold` parameter
- Formula/core score threshold alerts
- Volume/price confirmation alerts
- Price vs SMA crossover alerts (20/50/100/200)
- MACD bullish, SMA 50>200, Bollinger band alerts via TECHNICAL_TRIGGER
- Consecutive day trigger alerts (5+ up or down)
- Volume spike alerts via `vratio`
- RSI extreme alerts
- Fundamental change alerts via `fundamental_change_rows()`
- Alert performance tracker via `alert_precision_backtest()` for golden cross and RSI extreme
- Watchlist dashboard via `dashboard_cols`

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **No screen membership change detection (entry/exit)** | The spec describes ENTRY/EXIT signals comparing F(S,t) vs F(S,t-1). Implementation only checks current score thresholds — no prior state comparison |
| 2 | **No percentile rank shift alerts** | Spec describes UPCT shift detection. Not implemented |
| 3 | **No alert scheduling (daily/weekly)** | No job runner or scheduling infrastructure |
| 4 | **No email notification delivery** | Not wired |
| 5 | **Alert performance tracker lacks forward window tracking** | The `performance` table returns `precision_proxy=None` with note "requires persistent alert history". Only `alert_precision_backtest` provides some historical proxies |
| 6 | **No screen entry/exit log annotations on equity curve** | The spec describes annotating the backtest equity curve with entry/exit events. Not implemented |
| 7 | **No fundamental change alerts from scheduled quarterly comparison** | `fundamental_change_rows()` only checks `revenue_growth_yoy` and `eps_growth_yoy` from the current panel — not a true quarterly comparison |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | `VOLUME_SPIKE` alert double-fires via both the generic volume/price confirmation block (line 47) AND the explicit spike block (line 53-54) | feature_06.py:47-54 |
| 2 | The `fundamental_change_rows` threshold check uses `>= threshold` but the spec says "changed by more than X%" using `>` | analytics.py:1829 |
| 3 | `alert_precision_backtest` for RSI extreme recomputes RSI from the price matrix — this is correct but duplicates the existing RSI column from the panel | analytics.py:1754-1757 |
| 4 | The `screen_entry_exit_log` table is just tickers with score >= threshold, not a comparison against prior state | feature_06.py:65-66 |
| 5 | `VOLUME_PRICE_CONFIRMATION` alert has no spec reference — it's an ad hoc addition | feature_06.py:47-48 |

**Score: 4/10**

---

### F07 — Comparative Relative Valuation (feature_07.py: 46 lines)

**Spec targets:**
- Four-dimension valuation card: absolute value, universe percentile, sector percentile, own-history percentile
- Own-history percentile for W in {252, 756, 2520} days (1/3/10 years)
- For fundamentals: own-history over quarterly filing dates
- Sector valuation landscape heatmap: 11 sectors × J metrics
- Own-history percentile time series (re-rating indicator)
- OLS slope of own-history percentile over trailing 21 days
- Peer comparison table with better/worse indicators
- Valuation metric inversion for display

**Implemented:**
- Four-dimension card via `relative_valuation()`: absolute_percentile, sector_percentile, universe_percentile, own_history_percentile
- Own-history percentile via `own_history_percentile_blended_from_history()` (blend of PE/PB/PS/EV_EBITDA/EV_SALES)
- Sector valuation landscape heatmap via `relative_valuation()`: sectors × {PE, PB, PS, P/CF, EV/EBIT, EV/EBITDA, FCF yield}
- Own-history percentile time series via `own_history_series_from_history()` with re-rating/de-rating trend
- OLS re-rating slope via `re_rating_slope_from_series()` — slope per month
- Peer comparison table via `relative_valuation()`: sector/industry/market_cap_bucket/custom peer scope
- Universe percentile table

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **No 1/3/10 year window toggle for own-history** | Implementation uses all available history; the `history_window` payload parameter is passed but `_history_window` converts `"1y"` to 365 days via `DateOffset(years=int(years))`, not trading days. The spec requires windows in TRADING days (252/756/2520) |
| 2 | **Valuation metric inversion for display** | The spec says "for PE, PB, EV/EBITDA: invert all four dimensions before display so higher = cheaper." The peer_table uses `higher_better=False` in `rank_pct()` which inverts the percentile, but the raw values are not inverted |
| 3 | **No sector valuation landscape heatmap as 11×J matrix** | Implementation returns per-sector-per-metric rows with mean percentile values. The spec describes a proper heatmap matrix. The output format matches |
| 4 | **No fundamental-metric-specific history** | For fundamental metrics that update quarterly, the own-history percentile should be over available quarterly filing dates, not daily. The implementation uses `fundamental_history()` which is by reportDate, so this is correct for fundamentals but not for price-based metrics |
| 5 | **Per-metric universe percentile table** | The `universe_table` exists with `universe_percentile` per metric — matches spec |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | History percentile excludes current observation from reference set (correct) as fixed in the audit trail | analytics.py:2124-2131 |
| 2 | Sector heatmap uses `higher_better=False` (cheap = high percentile) for all metrics — but not all metrics are valuation metrics. Profitability metrics like FCF yield should NOT be inverted | analytics.py:2091 |
| 3 | The history series expanding percentile uses `(x <= x.iloc[-1]).mean() * 100` which always produces 100 for the last observation by design — this is intentional but confusing for UI display | analytics.py:2158 |
| 4 | `own_history_percentile_blended_from_history` takes the mean of percentiles across metrics — this dilutes strong signals from individual metrics | analytics.py:2138-2144 |
| 5 | Re-rating slope uses `np.polyfit(x, y, 1)[0]` where x is just `[0, 1, 2, ..., n-1]` — the slope is in percentile-points-per-observation, then multiplied by 21. But if data is quarterly, 21 periods may span over a year | analytics.py:2178 |

**Score: 6/10**

---

### F08 — Export and Integration (feature_08.py: 46 lines)

**Spec targets:**
- CSV, JSON, plain ticker list export formats
- Change report with entries/exits/rank shifts vs prior run
- Scheduled daily/weekly email delivery
- Portfolio optimizer feed
- Research notebook / ML feed
- API endpoint per saved screen
- Column selection

**Implemented:**
- TSV and JSON export via `build_export_payload()` with `tsv_preview` and `json_payload`
- Change report stub: `[{"field": "row_count", ... "status": "current_run"}]`
- API endpoint metadata: `{"method": "POST", "path": "/api/screener-v2/run", "status": "not_wired"}`

**Gaps:**
| # | Gap | Details |
|---|---|---|
| 1 | **No instant CSV download** | Only `tsv_preview` (first 5000 chars) and `json_payload` — no actual file download |
| 2 | **Change report is a stub** | No prior-run state comparison, no entries/exits/rank shifts |
| 3 | **No scheduled email delivery** | Not implemented |
| 4 | **No portfolio optimizer feed** | Not wired |
| 5 | **No research notebook / ML feed** | Not wired |
| 6 | **No API route registered** | Explicitly marked `not_wired` |
| 7 | **No plain ticker list export** | Not implemented |
| 8 | **No column selection UX** | Not implemented |
| 9 | **No watchlist creation from screen result** | Not implemented |

**Bugs/Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | The `export_format` parameter default is `"tsv"` but the spec says CSV. The format is tab-separated, not comma-separated | feature_08.py:16 |
| 2 | No `status: ok` response validation — the raw output rows may contain NaN/Inf which are cleaned by `clean_json()` but result column order is not deterministic | feature_08.py:27-28 |

**Score: 2/10**

---

## 3. Shared Infrastructure Audit

### `analytics.py` (2,254 lines) — Completeness, Math Correctness

**Strengths:**
- Comprehensive technical indicator computation: SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, stochastic, Williams %R, OBV, gap, consecutive days
- All use Wilder smoothing per spec (fixed in the audit trail)
- SMAs compute one rolling frame per window (optimized)
- beta_252, beta_universe_proxy, beta_effective with source tracking
- IVOL from FF3 residuals using OLS
- Amihud illiquidity with percentile
- Vol forecast (EWMA × sqrt(21)) — matches spec approximation but not the HAR model
- 52-week proximity score correct per George-Hwang 2004

**Math Issues:**
| # | Issue | Location |
|---|---|---|
| 1 | Gap formula uses `close_t / close_{t-1} - 1` not `(open_t - close_{t-1}) / close_{t-1}` | analytics.py:341 |
| 2 | Vol forecast uses EWMA, not Yang-Zhang/HAR from Vol module | analytics.py:373 |
| 3 | ROIC is not computed as a general metric — only `greenblatt_roic()` exists, which is a specific Greenblatt formula, not the spec's `ROIC = EBIT(1-t) / (Equity + Debt - Cash)` | analytics.py:1281-1304 |
| 4 | `earnings_yield` is computed as `1 / trailing_pe`, which is correct for TTM earnings yield. But the spec also wants `EBIT / EV` for Greenblatt's earnings yield | analytics.py:518 |
| 5 | `market_value_liabilities = market_cap / liabilities` is used for Altman Z but the spec defines X4 as `Equity / Total Liabilities` | analytics.py:505 |
| 6 | `relative_return_3m_spy` is computed twice (lines 365 and 367-368) — once in the else branch and once unconditionally. The first assignment (line 365) uses the universe mean as proxy, then the second (line 368) overwrites with true SPY return. This double-assignment is a code smell | analytics.py:365-368 |

**`clean_json` edge cases:**
- `np.bool_` types are not converted — will throw JSON serialization errors
- `pd.Timedelta` not handled
- `complex` not handled

### `data_loader.py` (240 lines) — Data Source Coverage

**Current sources:**
- OHLCV: parquet file (market_universe.parquet)
- Fundamentals: parquet (master_fundamentals.parquet)
- Ken French factors: CSV (ff5_daily.csv, momentum_daily.csv)
- Macro: parquet (category7_macro_regime.parquet)
- Hourly OHLCV: parquet (market_universe_hourly.parquet)

**Missing vs spec:**
| Source | Spec | Status |
|---|---|---|
| yfinance Ticker.info | Sector, exchange, metadata | ✅ via `latest_fundamentals()` |
| Ken French FF5 + Momentum daily | MKT-RF, SMB, HML, RMW, CMA, MOM, RF | ✅ via `load_factor_returns()` |
| FRED VIX / yield curve | Regime context | ✅ via `load_macro()` |
| SPY constituent list (ETF holdings) | S&P 500/400/600 proxies | ❌ Not implemented |
| Delisted ticker database | Survivorship-bias correction | ❌ Scaffold only |
| PIT fundamentals by as-of date | Point-in-time enforcement | ❌ Scaffold only |
| Alert state / prior run history | Change detection | ❌ Scaffold only |

The `_parse_ken_french_csv` function is robust — handles headers flexibly, converts percentages to decimals, handles multi-line footers.

**`parse_symbols` issues:**
- `sp500` alias exists but `russell`, `midcap`, `smallcap` aliases do not
- No custom CSV upload endpoint support
- When `raw` is an iterable, it normalizes each symbol but doesn't handle `pandas.Series` specifically (would need `.tolist()`)

### `gics.py` (77 lines) — GICS Classification

A static dictionary mapping 60+ industry labels to industry groups. Covers the major yfinance industry labels.

**Issues:**
| # | Gap | Details |
|---|---|---|
| 1 | Not a complete mapping | Only 60 entries; thousands of yfinance industry labels exist. Most will fall through to "Unclassified" |
| 2 | No sector→industry group mapping | Only industry→industry-group. No cross-validation that a given industry's group assignment is within the correct GICS sector |
| 3 | No sub-industry tier | Spec mentions sub_industry_i from yfinance Ticker.info — not implemented |
| 4 | No validation that GICS mapping is up to date | SPDR's 2023 GICS reclassification (Communication Services, etc.) — static dict may be outdated |

### `performance.py` (179 lines) — Caching, JIT, Optimization

**Strengths:**
- `lru_cache` with version-staleness detection via `mtime` — good invalidation strategy
- Pre-indexed market OHLCV by ticker for fast subset assembly
- Bounded caches: 384 close_matrix, 256 volume_matrix, 256 returns_matrix
- `symbol_key()` provides order-independent, de-duplicated, hashable keys
- All loaders return `.copy()` of cached data to prevent mutation

**Issues:**
| # | Issue | Details |
|---|---|---|
| 1 | `_market_ohlcv_by_ticker()` calls `cache_clear()` on `load_market_ohlcv()` to force re-read — this destroys the single-cache optimization on every version mismatch | performance.py:71-72 |
| 2 | `cached_fundamental_history` has `maxsize=None` (unbounded LRU) — for 5,000 tickers this is fine but should be documented | performance.py:145 |
| 3 | No cross-process cache — acknowledged as future work in missing.md |
| 4 | The version-stamp approach reloads the full parquet on every mtime change — for a 6GB parquet this can be slow | performance.py:56-57 |

### `screener_v2_combined.py` (3,025 lines) — Monolithic Dumping Ground

**Assessment:**
This file is an exact concatenation of `data_loader.py` + `gics.py` + `performance.py` + `analytics.py` into a single 3,025-line file. It is NOT imported by any feature module or by `registry.py` — the feature modules all import from `core.analytics`. The combined file appears to be a stale snapshot or a build artifact.

**Specific issues:**
| # | Issue | Details |
|---|---|---|
| 1 | **3025 lines of duplicated code** | Every line in this file is a copy of the standalone core modules. This doubles the effective codebase |
| 2 | **Diverge from standalone files** | The combined file's `_field_time_matrix` does NOT have the `RETURN_HORIZON_FIELDS` mapping present in analytics.py. The combined file's `academic_strategy_scores` lacks the full QMJ implementation. The combined file's `_time_series_call` lacks PIT fundamental formula support |
| 3 | **No imports from standalone modules** | The combined file has its own inline copies of `from .data_loader import ...` and `from .gics import ...` — these are circular imports with the standalone modules |
| 4 | **No test coverage** | There is no indication that the combined file is tested independently |
| 5 | **Maintenance liability** | Any fix to analytics.py must be duplicated to the combined file, which will almost certainly drift |

**Recommendation: Delete `screener_v2_combined.py`** — it is unused, duplicated, and has already diverged from the live modules.

### `registry.py` (65 lines) — Module Loading

**Strengths:**
- Clean `ScreenerFeature` dataclass for metadata
- `_load()` tries two path prefixes — handles dev/prod layout differences
- `run_feature(feature_id, payload) -> dict` follows the same convention as ML V2 and Volatility V2
- `get_feature()` supports both "01" and "feature_01" id formats

**Issues:**
| # | Issue | Details |
|---|---|---|
| 1 | `_load()` catches `ModuleNotFoundError` broadly — if the module has an import error other than not-found, it raises unclear errors | registry.py:21-23 |
| 2 | `run_feature` silently merges `payload` with `{}` — if payload is None, it passes an empty dict, which may be unexpected for features that require parameters | registry.py:65 |
| 3 | No feature-level timeout or error isolation — a long-running or crashing feature blocks the caller | registry.py:64 |

### `fetchers/fetch_missing_data.py` (101 lines) — External Data Acquisition

Well-structured scaffold with clear `append_parquet()` helper that:
- Never overwrites
- Drops duplicates by subset
- Creates parent directories as needed
- Lists all 5 missing datasets with append keys

**Issues:**
| # | Issue | Details |
|---|---|---|
| 1 | Fetch functions raise `NotImplementedError` — not safe to call in production | fetch_missing_data.py:97 |
| 2 | No fetcher is wired to any scheduler or cron job | |
| 3 | `append_parquet` loads the entire existing parquet into memory on every append — for datasets with millions of rows this will fail | fetch_missing_data.py:76-78 |

### Overall Architecture Quality

**Strengths:**
- Clean `feature_XX.py` / `registry.py` / `run_feature(payload) -> dict` pattern matching ML V2 and Volatility V2
- Read-only data layer from local parquet files
- Well-documented gaps in README, FEATURES.md, NOT_POSSIBLE_WITH_CURRENT_DATA.md, missing.md
- Deterministic computations — no random seeds without explicit reproducibility
- JSON-safe response pipeline via `clean_json`
- Version-stamped caches in performance layer

**Weaknesses:**
- 3,025-line duplicated combined file — architectural smell
- `analytics.py` at 2,254 lines should be split: compute_screener.py, formula_engine.py, academic_scores.py, backtest.py, alerts.py, relative_valuation.py
- Feature runners are thin wrappers (avg 80 lines) — good. But all heavy logic is in a single analytics.py, which is not thin
- No shared schemas for filter payloads — each feature defines INPUTS but `apply_filters()` reads from arbitrary payload keys with no validation
- No error boundaries between feature calls — an exception in `metric_panel()` crashes the entire feature
- No async support — all computations are synchronous
- No unit tests visible in the codebase for these modules

---

## 4. API Layer Audit (screener_api.py)

**Key Finding: Screener V2 is NOT wired to the API layer. The existing API routes use V1 services exclusively.**

| Route | V1 Backend | V2 Use |
|---|---|---|
| `POST /screener/evaluate` | `screener_evaluator.py` + `screener_state.py` | None |
| `GET /screener/universes` | `universe.py` | None |
| `GET /screener/indicators` | `screener_evaluator.py` | None |
| `GET /screener/tradeable-universe` | `screener_quant360.py` | None |
| `GET /screener/trend-quality` | `screener_quant360.py` | None |
| `GET /screener/volatility` | `screener_quant360.py` | None |
| `GET /screener/regime` | `screener_quant360.py` | None |
| `GET /screener/liquidity` | `screener_quant360.py` | None |
| `GET /screener/rotation` | `screener_quant360.py` | None |
| `GET /screener/events` | `screener_quant360.py` | None |
| `GET /screener/stress` | `screener_quant360.py` | None |
| `GET /screener/summary` | `screener_quant360.py` | None |
| `POST /screener/backtest` | **Stubbed (random)** | None |
| `GET /screener/company` | `robust_data_fetcher.py` | None |
| `GET /screener/chart` | `data_engine.py` / yfinance | None |

**V1 Architecture Notes:**
- V1 is a separate universe focused on INDIAN equities (`.NS`, `.BO` tickers), CRYPTO, FX, etc.
- V1 uses `yfinance` directly via `yf.Ticker()` for individual stock lookups
- V1 has a sophisticated multi-source data fetcher (`robust_data_fetcher.py`)
- V1's `screener_quant360.py` (1,539 lines) is a monolithic service with 8+ tab endpoints
- V1 has saved scans with in-memory storage (no persistence)
- V1 backtest endpoint returns random numbers (`random.uniform`) — this is a placeholder
- V1 formula parser exists in `screener_evaluator.py` — appears to be a separate implementation from V2's `FormulaEngine`

**V1 ↔ V2 Mismatch:**
| Dimension | V1 | V2 |
|---|---|---|
| Universe | India (NS/BO) + US + Crypto + FX | US only (yfinance symbols) |
| Service model | Monolithic `screener_quant360.py` | Feature modules + registry |
| Formula parser | `get_formula_parser()` | `FormulaEngine` |
| Data sources | yfinance live + cache | Local parquet files |
| Backtest | Random stub | Deterministic from price history |
| Saved screens | In-memory dict | Not implemented |
| Risk-free rate | Not used | Ken French RF |

**API Design Quality:**
- The V1 API is well-structured with clear `APIRouter`, Pydantic models, and descriptive docstrings
- The V1 API mixes async (FastAPI) with synchronous yfinance calls — this will block the event loop
- The `/screener/backtest` endpoint returning random numbers is a production blocker
- V1 `/screener/company` endpoint is 220+ lines with deep nested try/except — fragile

**Recommendation:** V2 features should be exposed as `/screener-v2/run/{feature_id}` or via a new `APIRouter(prefix="/screener-v2")`. The existing V1 routes can coexist.

---

## 5. Documentation Quality

| Doc | Lines | Assessment |
|---|---|---|
| `README.md` | 107 | Excellent. Clear summary of what's done, what's missing, smoke test results, data inventory |
| `FEATURES.md` | 28 | Good checklist. Honest about "Not Fully Production-Complete" |
| `NOT_POSSIBLE_WITH_CURRENT_DATA.md` | 71 | Excellent. Comprehensive gap analysis across data, infrastructure, and computation. Clearly distinguishes "not possible" from "implemented proxies" |
| `missing.md` | 485 | Very thorough. Documents 6+ attachment passes chronologically with granular per-feature checklists and exact formula audit notes. Reads as a running log of implementation history |

**Issues:**
| # | Issue |
|---|---|
| 1 | `FEATURES.md` says saved_screens persistence is "output key exists" — F01 returns `saved_screens: []` which is an empty list, not a proper "not implemented" marker |
| 2 | `NOT_POSSIBLE_WITH_CURRENT_DATA.md` lists implemented proxies but doesn't mention that `screener_v2_combined.py` is a stale duplicate |
| 3 | missing.md is very detailed but duplicates many items between attachment passes — consolidating would be cleaner |
| 4 | README says "Smoke-ran S1-S8 with a 10-symbol local universe" — no mention of testing with the full 5,000-ticker universe |

**Comparison to ML V2 / Volatility V2 READMEs:**
The Screener V2 documentation is more thorough than a typical module README. The `NOT_POSSIBLE_WITH_CURRENT_DATA.md` and `missing.md` files are examples of honest engineering documentation that ML V2 and Volatility V2 would benefit from.

---

## 6. Overall Assessment

### Total Lines of Code

| Category | Files | Lines |
|---|---|---|
| Core infrastructure (unique) | 4 | 2,750 |
| Core combined (duplicate) | 1 | 3,025 |
| Feature runners | 8 | 653 |
| Registry + init | 3 | 71 |
| Fetchers | 1 | 101 |
| **Total unique** | **17** | **3,575** |

### Missing Functions/Models from Spec

| Feature | Missing | Impact |
|---|---|---|
| S1 | ROIC computation, Russell 1000/S&P400/S&P600 proxies, user-settable technical periods | Some filters use hardcoded periods; universe selection limited |
| S1 | Saved screens, scheduled re-run, CSV upload | No persistence |
| S2 | 12+ template formulas, walk-forward backtest, ICIR, historical date picker | Only 5 templates; no ICIR computation |
| S2 | `if()` function replaced with `where()` | Spec formulas need translation |
| S2 | Proper time-series support for all fields (price-only matrix) | Non-price fields use panel-order approximation |
| S3 | Walk-forward IC-IR weighting, ridge walk-forward, regime-conditional IC | Weights are bootstrap cross-sectional |
| S4 | Proper QMJ implementation in combined.py | Combined file has proxy QMJ |
| S4 | Proper Graham Net-Net, Dogs of the Dow, Mohanram G-Score | Proxies or placeholders |
| S5 | Point-in-time validation, survivorship correction, proper Monte Carlo PBO | Acknowledged and documented |
| S5 | Correct transaction cost calculation (spread across all days) | Costs are mathematically wrong |
| S6 | Persistent alerts, percentile rank shift alerts, email delivery | Stubs |
| S7 | User-selectable history window (252/756/2520 trading days) | Uses DateOffset(years=) |
| S8 | CSV download, API route, prior-run comparison, scheduled delivery | Stubs |

### Data Dependency Gaps

| Dataset | Status | Blocks |
|---|---|---|
| PIT fundamentals by as-of date | Scaffold only | S5 true backtests, S4 academic historical screens, S3 walk-forward ICIR |
| Delisted securities | Scaffold only | S5 survivorship correction |
| Screen run history | Scaffold only | S8 change report, S6 alert history |
| Saved screen definitions | Scaffold only | S1 saved screens, S6 watchlist |
| Alert state/delivery log | Scaffold only | S6 persistent alerts |
| Job runner / scheduler | Not started | S5 scheduled re-runs, S6/S8 delivery |
| API routes | Not wired | All features inaccessible from frontend |

### Code Quality Rating: **5/10**

**Positives (+):**
- Clean `run(payload) -> dict` pattern matching other V2 modules
- Excellent documentation of gaps and limitations
- Robust data caching with staleness detection
- Consistent JSON-safe output handling
- Formula engine with `ast.parse` is elegant
- Wilder smoothing and spec-compliant technical indicators

**Negatives (-):**
- 3,025-line duplicated combined file
- 2,254-line analytics.py should be split
- No test files discovered
- No async support
- No error isolation between features
- Transaction cost model is mathematically incorrect
- Gap formula is wrong (uses close-close not open-close)
- V1 API not wired to V2 features
- Several academic strategies are proxies, not spec-compliant

### Overall Rating: **4/10**

The implementation has the right architecture (registry + feature modules + `run()` convention) and correctly computes most technical indicators and fundamental metrics. However:

1. **3,025 lines of duplicated code** must be deleted or reconciled
2. **The V2 features are invisible from the API** — no routes exist
3. **The "code is not the spec" gap is wide**: S2, S5, S6, S8 have large missing functionality
4. **Critical mathematical errors** (gap formula, ROIC missing, transaction cost model) degrade trust in results
5. **The missing datasets (PIT fundamentals, delisted securities) are fundamental** to the value proposition of S5 and S3 walk-forward weighting

### Top 10 Critical Fixes (Priority Order)

| # | Fix | File(s) | Effort |
|---|---|---|---|
| 1 | **Delete `screener_v2_combined.py`** | `core/screener_v2_combined.py` | 5 min |
| 2 | **Wire V2 feature route** via `APIRouter(prefix="/screener-v2")` calling `registry.run_feature()` | New file or `screener_api.py` | 1 day |
| 3 | **Fix gap formula** — use `(open - prior_close) / prior_close` | `core/analytics.py:341` | 5 min |
| 4 | **Fix transaction cost model** — deduct on rebalance dates only, not spread across all days | `core/analytics.py:1660-1661` | 30 min |
| 5 | **Add spec-compliant ROIC** as `EBIT(1-t) / (Equity + Debt - Cash)` — not just Greenblatt ROIC | `core/analytics.py` | 1 hour |
| 6 | **Implement full QMJ in combined.py or delete combined.py** — the standalone analytics.py already has it; delete combined.py | `core/screener_v2_combined.py` | 5 min |
| 7 | **Add `if()` function alias** so raw spec formulas work without `where()` renaming | `core/analytics.py:862` | 5 min |
| 8 | **Fix holding-period sensitivity** — actually vary the forward return horizon, not just `rebalance_days` | `features/feature_05.py:70-71` | 1 hour |
| 9 | **Add user-settable technical indicator periods** (RSI, MACD, Bollinger, ATR, ADX) | `core/analytics.py:latest_technical_features` | 2 hours |
| 10 | **Split `analytics.py` into domain modules** — `technical.py`, `fundamental.py`, `formula.py`, `backtest.py`, `alerts.py`, `relative_val.py`, `academic.py` | `core/` | 1-2 days |

---

*Audit performed 2026-07-13 against spec documents `screener features.md` (378 lines) and `screener computation.md` (1,855 lines). All line numbers refer to files in `backend/app/services/screener_v2/`. The `core/screener_v2_combined.py` referenced in this review is a ~3,025-line duplicate of the individual `core/*.py` files.*
