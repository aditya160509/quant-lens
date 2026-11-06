# ML V2 frontend: output-by-output design plan

Date: 2026-10-05. Scope: 12 features, about 110 outputs from `feature_manifest()`. The plan reuses the Research V2 workspace: the `.ws` shell, `OutputCard` (view-as menu, overlay, pin, width), `explore.tsx`, the `charts/*` family (TimeSeries, Heatmap, Diverging, DotGrid, dataWindow), `StudyForm` (Quick/Standard/Expert levels, depends_on, units) and the jobs/polling hooks. ML V2 should be a new module that shares those primitives. It does not fork them.

Quality bar: each output must answer one question at a glance, show its uncertainty, and name its reference method in a footnote. The backend contract the agent is writing is `docs/ML_V2_CONTRACTS.md`. Renderers bind to it.

## 0. What makes this module different (the reason to pay)

1. **Honesty is visible.** Every card shows a status chip (live, conditional or unavailable with the reason) and a leakage stamp (purge/embargo days, train/test dates). No other retail tool shows the purge.
2. **Distributions, not points.** CPCV gives many paths, so Sharpe is a violin with DSR and PBO beside it, not one number.
3. **One timeline across features.** Regime shading (F06) can be overlaid on any time series in F02, F03, F07, F08 and F09 through the existing `overlay()` view option.
4. **Per-output view choice** (already built for Research): every table can also be shown as a chart and every chart as a table, with role-aware defaults.

## 1. New shared renderers to build once (beyond Research V2)

| Renderer | Used by | Reference |
|---|---|---|
| `FoldMatrix`: split × fold grid, coloured train/test/purge/embargo | F01 | skfolio `plot_train_test_index`: https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html ; purgedcv path figure: https://github.com/eslazarev/purged-cross-validation |
| `PathFan`: many equity paths, quantile band, median bold, best/worst labelled | F01, F05 walk-forward | purgedcv audit notebook §6–7: https://github.com/eslazarev/purged-cross-validation/blob/main/examples/backtest_overfitting_audit.ipynb |
| `Beeswarm`: SHAP value on x, feature rows, colour = feature value | F02 | https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/plots/beeswarm.html |
| `Waterfall`: base value → prediction, sorted contributions, "+N other" | F02 | https://shap.readthedocs.io/en/stable/generated/shap.plots.waterfall.html |
| `Dendrogram` with an optional reordered-heatmap underlay and cluster boxes | F05 | skfolio HRP example: https://skfolio.org/auto_examples/clustering/plot_1_hrp_cvar.html ; Riskfolio `plot_clusters`: https://riskfolio-lib.readthedocs.io/en/latest/plot.html |
| `RegimeBands`: background state shading plus a stacked-probability strip beneath | F06, and an overlay everywhere | TradingView HMM strip: https://www.tradingview.com/script/ggqF9HsV-Hidden-Markov-Model-Baum-Welch-UAlgo/ ; tear-sheet layout: https://github.com/Yosri-Ben-Halima/hmm-market-regime-engine |
| `StackedShare` (100% area) with a hover readout per date | F07, F08 weights | the line-width-illusion caveat (use sorted stacking plus a hover readout): https://inforiver.com/insights/stacked-area-charts-an-overview/ |
| `BarrierEvent`: a price path with upper/lower/vertical barriers and a first-touch marker | F04 | AFML triple barrier: https://random-docs.readthedocs.io/en/latest/implementations/tb_meta_labeling.html ; https://krew-solutions.github.io/trading-ml/architecture/ml/triple_barrier/index.html |
| `ZBand`: spread z-score with ±entry/exit bands and trade markers | F09 | Palomar ch. 15.6: https://bookdown.org/palomar/portfoliooptimizationbook/15.6-kalman-pairs-trading.html |
| `CoefCI`: dot-whisker, sorted, with a zero line and an optional OLS ghost dot | F11 | DoubleML `plot_effects`: https://docs.doubleml.org/stable/api/generated/doubleml.did.DoubleMLDIDAggregation.html ; https://docs.doubleml.org/stable/guide/se_confint.html |
| `ForceGraph`: correlation or cointegration network, edge weight = strength | F06, F09 | Riskfolio `plot_clusters_network` (link above) |

Charts stay in the existing d3/visx family. Do not add Plotly or ECharts.

## 2. Feature by feature

Notation: **Default view** → alternatives in the view menu. ★ marks the hero card for the feature.

### F01 CPCV engine
| Output | Default view | Why / unique touch |
|---|---|---|
| ★ cpcv_sharpe_distribution | Violin + strip of path Sharpes, with DSR and PBO badges | The question is "is the Sharpe real?", so show the spread with the median, worst and best labelled. |
| backtest_paths_chart | `PathFan` | Median bold, 5–95% band, worst path dashed. |
| purged_vs_naive_cv_comparison | Dumbbell (naive → purged per metric) | The leakage gap is the length of the bar. |
| probability_of_backtest_overfitting | Zone gauge (0 / 0.5 chance / 1) with the logit histogram | Reuses the VitalityGauge zone ruler. |
| deflated_sharpe_ratio | KPI plus the haircut arrow observed → deflated | Footnote cites Bailey–López de Prado 2014. |
| embargo_sensitivity | Line over embargo 0/5/10/21 with a CI | A flat line means robust. |
| per_fold_performance, cpcv_path_metrics | Table with sparkline cells → heatmap | |
| (new from metadata) fold layout | `FoldMatrix` | Makes the purge visible, which no competitor shows. |

### F02 GBT alpha
| Output | Default view | Notes |
|---|---|---|
| ★ prediction_rank_table | Ranked table: score bar, decile chip, top-3 SHAP drivers inline | Click a row to open its waterfall. |
| shap_feature_importance | Horizontal bar of mean abs SHAP → beeswarm toggle | |
| shap_beeswarm | `Beeswarm` | Cap at 2,000 dots and say so. |
| shap_waterfall_top_signal | `Waterfall` | Ticker picker. |
| model_ic_leaderboard | Dot plot of IC ± SE by model, ensemble highlighted | |
| rolling_monthly_ic_series | Bars (± colour) + 12-month MA line | alphalens IC tearsheet style: https://github.com/quantopian/alphalens |
| tuning_trials | Optuna-style trial scatter (trial# vs score, best-so-far step line) | Plus a parameter-importance bar if present. |
| model_performance, heldout_predictions, current_predictions, training_audit | Tables; audit as a key-value "receipt" card | The audit receipt shows train/test dates, purge and the n of the training set. |

### F03 Vol forecasting
| Output | Default view | Notes |
|---|---|---|
| ★ vol_forecast_panel | Realized vol line + forecast with an interval fan beyond the last date | Forecast region tinted. |
| realized_vs_predicted | Scatter with a 45° line + QLIKE/MSE badges → time-series overlay | Stefan Jansen GARCH notebook pattern: https://github.com/stefan-jansen/machine-learning-for-trading/blob/main/09_model_based_features/08_garch_volatility.py |
| vol_term_structure | Line across horizons, today vs 1M ago ghost | |
| garch_leverage_news_impact_curve | NIC curves per model on one axis, asymmetric shading | Sheppard slides definition: https://www.kevinsheppard.com/files/teaching/mfe/slides/univariate_volatility_slides_2021-2022-presentation.pdf |
| garch_model_selection | Table sorted by AIC with Δ-AIC bars | |
| forecast_tournament | Leaderboard by loss, Diebold–Mariano-style dots if present | |
| ensemble_vol_forecast_weights | `StackedShare` | |
| forecast_error_distribution, model_confidence_intervals, realized_vol_estimator_comparison, forecast_rows | Histogram / interval table / multi-line | |

### F04 Triple barrier and meta-labeling
| Output | Default view | Notes |
|---|---|---|
| ★ barrier_hit_path_examples | `BarrierEvent` small multiples (TP hit, SL hit, timeout, ambiguous) | Ambiguous same-bar hits drawn hatched, matching the null label. |
| triple_barrier_label_distribution | Stacked bar (+1/0/−1) per period | |
| event_outcome_timeline | Price with event dots coloured by outcome | |
| meta_label_probability_distribution | Histogram split by true label, with a threshold slider | |
| cqr_coverage_audit | Nominal vs empirical coverage bars with a target line | |
| cqr_interval_width_distribution | Histogram | |
| barrier_sensitivity_surface | Heatmap (pt × sl) with the chosen cell outlined | |
| label_method_comparison, label_audit, barrier_parameters, barrier_sensitivity | Tables | |

### F05 HRP / NCO / BL
| Output | Default view | Notes |
|---|---|---|
| ★ hrp_weight_vector | Bar of weights coloured by cluster → treemap | |
| cluster_dendrograms | `Dendrogram` | |
| quasi_diagonalized_covariance_heatmap | Heatmap in leaf order with cluster boxes | |
| risk_contribution_decomposition | Bar of risk contribution with an equal-risk reference line | Riskfolio `plot_risk_con` style with `erc_line`. |
| walk_forward_allocation | `StackedShare` over rebalance dates + turnover bars | |
| black_litterman_posterior_return_vector, bl_vs_pure_hrp_weight_comparison | Dumbbell prior → posterior; diverging weight-diff bar | |
| hrp_weights, allocation_training_audit, black_litterman | Tables / receipt | |

### F06 Regimes
| Output | Default view | Notes |
|---|---|---|
| ★ regime_probability_time_series | `RegimeBands`: index price with state shading over a stacked-probability strip | It also becomes a global overlay. |
| regime_transition_heatmap / transition_matrix | Heatmap with expected-duration labels (1/(1−p_ii)) | |
| current_regime_probabilities | Big state chip + probability bars + days in state | |
| regime_conditional_asset_returns | Grouped dot plot (state × asset), with CI | |
| pc1_variance_monitor | Line + threshold + alert markers | |
| correlation_network_density | Line; click a date to see the `ForceGraph` snapshot | |
| ensemble_vs_hmm_comparison, parallel_gmm_regime_probabilities, training_audit | Agreement bar / small multiples / receipt | |

### F07 DMA / online learning
| Output | Default view | Notes |
|---|---|---|
| ★ model_weight_evolution | `StackedShare` with regime overlay available | |
| live_model_weight_dashboard / current_model_weights | Ranked weight bars + Δ vs 1M | |
| obs_regret_curve / obs_regret_log | Cumulative regret vs best-in-hindsight line, √T guide | Regret framing per Pacchiano et al.: https://proceedings.mlr.press/v238/dann24a/dann24a.pdf |
| dma_vs_obs_vs_static_bma | Cumulative loss lines | |
| prediction_calibration_curve | Reliability diagram (45° line) + counts histogram | |
| obs_weight_evolution, model_performance_tracker, score_log, training_audit | StackedShare / table / receipt | |

### F08 Composite optimizer
| Output | Default view | Notes |
|---|---|---|
| ★ long_short_backtest | Equity + drawdown underwater (Research TimeSeries) | quantstats-like: https://github.com/ranaroussi/quantstats |
| ic_weighted_composite_weights / factor_weights | Diverging bar | |
| walk_forward_weight_stability | Heatmap (factor × date) → StackedShare | |
| factor_correlation_heatmap | Clustered heatmap | |
| composite_signal_distribution | Histogram by decile | |
| latest_composite_scores, training_audit | Ranked table / receipt | |

### F09 Pairs
| Output | Default view | Notes |
|---|---|---|
| ★ spread_zscore_timeseries | `ZBand` with entry/exit markers | |
| pair_candidate_leaderboard / pair_candidates | Table: p-value, half-life, correlation, sparkline of spread | |
| hedge_ratio_path / hedge_ratio | Line, static OLS dashed for comparison | Palomar Fig 15.21 idea. |
| pair_backtest_equity | Equity + drawdown | |
| entry_exit_signal_timeline | Both legs normalized with trade spans shaded | |
| cointegration_network | `ForceGraph` (edge = 1−p) → p-value clustermap | |
| spread_timeseries, training_audit | Line / receipt | |

### F10 Microstructure
| Output | Default view | Notes |
|---|---|---|
| ★ microstructure_ic_leaderboard / ic_leaderboard | IC ± SE dot plot by signal | |
| amihud_illiquidity_surface / amihud_time_surface | Heatmap (date × size bucket) | |
| roll_spread_cross_section, corwin_schultz_spread_cross_section | Histogram + top-N table | |
| 52_week_high_proximity_heatmap | Heatmap sorted by proximity | |
| ivol_cross_sectional_sort, max_factor_distribution | Quintile bars / histogram | |
| hl_amihud_vs_standard_amihud | Scatter with 45° line | |
| volume_surprise_signal, liquidity_regime_monitor, signal_backtest | Line / bands / equity | |
| microstructure_signal_correlation_matrix, microstructure_table | Heatmap / table | |

### F11 Conditional factor association (DML)
| Output | Default view | Notes |
|---|---|---|
| ★ conditional_ape_leaderboard | `CoefCI` sorted by APE, OLS ghost dot | The gap between the dots is the confounding adjustment. |
| adjustment_vs_univariate_slope | Scatter (univariate vs DML) + 45° line | |
| ape_time_series | Line with CI ribbon | |
| robust_inference_table / conditional_ape_table | Regression-style table (coef, SE, t, stars) | modelsummary look, already in Research. |
| unidentified_factors | Callout list with the reason | |

### F12 Sequence models
| Output | Default view | Notes |
|---|---|---|
| ★ architecture_comparison | Dot plot of OOS IC ± SE per architecture, runtime as a size or second axis | |
| monthly_oos_ic | Bars + MA per architecture (small multiples) | |
| training_loss | Train/val loss curves per architecture, best-epoch marker | |

## 3. Page structure (mirrors Research V2)

Six pages, grouped by the question each answers:

1. **Validate**: F01.
2. **Predict**: F02, F12.
3. **Risk & vol**: F03, F04.
4. **Allocate**: F05, F08.
5. **Regimes & adapt**: F06, F07.
6. **Relative value & microstructure**: F09, F10, F11.

Keep: Overview stats strip, Board pins, Dock compare, the `?s=` settings link and embed mode.

## 4. Build order

1. Module shell plus manifest-driven form: reuse `StudyForm` against the new contract.
2. Shared renderers in §1, each with a fixture-driven Playwright snapshot.
3. Hero card per feature (★), then the remaining outputs.
4. Regime overlay across modules.
5. Browser pass: desktop and mobile, light and dark.
