# ML V2: the max pass

Date: 2026-10-05. Baseline: commit a1c6c908, where all 12 features run end to end at `/ml`. This file is the bar and the checklist for making it best in class. Status marks: [ ] open, [x] done.

## The quality bar

Each output must meet all six of these:

1. **One question, answered at a glance.** The title asks it, the chart answers it, and a one-line reading says the answer in words.
2. **Uncertainty is visible.** Intervals, bands or spreads appear wherever the number is an estimate.
3. **Honest provenance.** The card shows the train and test window, purge and embargo, and the universe. Anything unavailable says why.
4. **Readable at a glance.** No more than about 12 series or 20 categories without grouping. Axis titles carry units. Numbers use consistent formats: percent for returns and weights, 3 decimals for IC and t.
5. **Interactive where it helps.** Hover shows exact values. Clicking drills down. Charts that share dates share the crosshair.
6. **Works everywhere.** Dark and light themes, desktop and phone width (360 px), keyboard, and screen-reader labels.

The page as a whole must meet these:

- A hero that answers the feature's question, then supporting evidence, then the data.
- A verdict line on every feature, coloured green, amber or red against a stated threshold.
- Defaults that run in under 20 seconds and show something interesting.

## Checklist

### A. Outputs (designed views and readings)

- [ ] A1. **One-line reading on every card**, built from templates with no AI. Examples: "IC positive in 4 of 7 months (mean 0.050, IR 0.31): weak but consistent." and "HAR-Ridge wins at 1 and 5 days; GBM at 21."
- [ ] A2. **Designed views for every remaining auto card:**
  - F03: news-impact curves, estimator comparison
  - F04: event timeline and meta-probability by label
  - F06: PC1 monitor with threshold markers
  - F10: cross-section bars sorted with a median line, liquidity monitor with stress bands
  - F12: monthly IC heatmap with a mean row
- [ ] A3. **Readable dense charts:**
  - Correlation matrices above 20 names collapse to cluster blocks, with expand on click.
  - Multi-series lines show the top 6 and fade the rest, with a legend that isolates on click.
  - The beeswarm shows the top 12 features.
- [ ] A4. **Axis titles and units on every chart.** Percent for returns, vol and weights. Annualised where stated.
- [ ] A5. **Benchmarks on performance charts:** equal-weight universe and SPY buy-and-hold beside each equity curve, plus a cost-free ghost line.
- [ ] A6. **Per-card provenance chip:** train/test dates and purge/embargo, from `training_audit` and meta.

### B. Interaction

- [ ] B1. Clicking a name in the ranking opens its SHAP waterfall. The ticker picker on the waterfall card does the same.
- [ ] B2. Clicking a pair in the leaderboard or network loads that pair's spread and z-band. This needs the backend to return the top N pair series.
- [ ] B3. Hovering a regime band highlights those dates on every time series on the page, and offers "shade regimes" on any time series in ML.
- [ ] B4. Clicking a cell in the barrier sensitivity surface reruns the study with that profit-taking/stop-loss pair.
- [ ] B5. Clicking a CPCV split row highlights its test dates on the path fan.

### C. Experience

- [ ] C1. **Pipeline hand-offs:**
  - "Use these predictions" from F02 sends them into F04 (primary side), F05 (views) and F08 (factor).
  - "Use these regimes" from F06 sends them into F03 and F07.
  - Each hand-off needs a backend artifact id.
- [ ] C2. **ML compare:** two runs side by side, aligned on the same metrics (IC, Sharpe, drawdown, coverage), with the differences highlighted.
- [ ] C3. **Universe presets:**
  - US large caps (the default)
  - one per sector
  - high-volatility names
  - ETFs only
  - a custom list
  - "the same universe as the last run"
- [ ] C4. **ML wording everywhere:** empty states, the Run button ("Train and test"), and the progress stages shown by the API.
- [ ] C5. **Overview as a dashboard:** the latest verdict per feature, current regime, today's top 5 names, current volatility forecast and the live pair, each linking to its page.
- [ ] C6. **First-run guide:** three steps (validate a model, read today's ranking, size with barriers), hidden after three runs.

### D. Visual polish

- [ ] D1. A side-by-side pass against the QuantConnect, Koyfin and TradingView screenshots for:
  - card density (14 px body, 12 px labels)
  - spacing on an 8 px grid
  - one accent colour
  - up/down colours used only for signed values
- [ ] D2. Equal hero heights per page, with KPI strips aligned to a 4-column grid.
- [ ] D3. Light theme reviewed on every page. Fix the e2e light snapshots, which currently render dark.
- [ ] D4. Phone width (360 to 760 px): cards stack, tables scroll inside the card, charts keep at least 240 px of height.
- [ ] D5. Loading skeletons shaped like each card's chart, not generic boxes.

### E. Backend support needed

- [ ] E1. Top-N pair series (for B2) and per-ticker SHAP for every ranked name (for B1). F02 already returns 256 beeswarm rows, which may be enough.
- [ ] E2. Artifact ids for predictions and regimes (for C1).
- [ ] E3. F07 and F10 results under 1 MB: drop the duplicated chart and table payloads (RAM plan step 6).
- [ ] E4. F12 runs two architectures by default (MLP and PatchTST) within 30 seconds.
- [ ] E5. Benchmark series (equal-weight and SPY) in every backtest output (for A5).

## Order

1. A1, A4, A6 (readings, axes, provenance): the biggest jump in perceived quality.
2. A2, A3, B1, B3, B5: designed views and in-page interaction.
3. D1 to D5: the visual pass.
4. E1 to E5, then B2, B4, C1, C2: needs backend work.
5. C3 to C6.
