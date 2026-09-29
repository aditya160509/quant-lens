## Implementation Checklist — Codex Pass 2026-05-12

This checklist is the honest repo implementation status for the extra output ideas below.

- [x] F01 multi-factor valuation gauge panel: backend now auto-expands single-factor requests to the default five factor set for dashboard/correlation output; frontend renders `multiFactorGaugePanel`.
- [x] F01 annotated percentile time series: frontend renders `annotatedTimeSeries` with 30/70 zones, brush, and crisis anchor legend; backend returns `crisis_anchors`.
- [x] F01 live alert feed: backend returns enriched alert rows; frontend renders `alertFeed`.
- [x] F01 null-safe valuation output: `lookback_days=None` no longer crashes; valuation table rows are filled with deterministic defaults where local regression fields are unavailable.
- [x] F02 animated rolling exposure heatmap: backend returns 12 deterministic rolling snapshots from current exposure data when real historical holdings are absent; frontend renders `rollingHeatmap`.
- [x] F04 current regime trend panel: backend returns current/30D/90D probability deltas; frontend renders `regimeTrend`.
- [x] F05 factor signal power radar: backend returns normalized radar axes from IC, ICIR, half-life, fit quality, and sign consistency; frontend uses existing radar renderer.
- [x] F07 decile return panel: backend returns a 10-bucket realtime decile proxy interpolated from actual quintile output; frontend renders `decileReturn`.
- [x] F08 hierarchical clustered heatmap: frontend renders `hierarchicalHeatmap` using the existing cluster sort path.
- [x] Build verification: `npm run build` passed for all Factors V2 pages.
- [x] Runtime verification: changed backend endpoints F02-F08 returned HTTP 200 with the new chart/table keys.
- [x] F02 true multi-portfolio side-by-side comparison: backend now returns `multi_portfolio_comparison` from current holdings plus comparison tickers/benchmarks; frontend renders `multiPortfolioCompare`.
- [x] F03 stacked active-return waterfall and decision freshness score: backend now returns `stacked_active_return_waterfall` and `decision_freshness_score`; frontend renders dedicated stacked and freshness-score panels.
- [x] F04 regime sensitivity table: backend now returns `regime_sensitivity` using supplied factor exposures or equal-factor defaults; frontend wires it as a signed table.
- [x] F05 cross-sector decay: backend now returns `cross_sector_decay` using master-universe sector dispersion adjusted horizon ICs; frontend renders `crossSectorDecay`.
- [x] F05 multi-factor radar overlay: backend now returns `multi_factor_power_radar` for up to six factors; frontend renders `multiFactorRadar`.
- [x] F06 crowding return overlay/crash annotation extras: backend now returns `crowding_return_overlay` and `crash_annotations`; frontend renders the overlay and annotation log.
- [x] F07 ADV capacity curve inside backtest: backend now returns `adv_capacity_curve`; frontend renders `advCapacityCurve`.
- [x] F08 crisis preset comparison controls: backend now returns `crisis_preset_comparison`; frontend renders preset tabs over normal/crisis/delta heatmaps.
- [x] UI cleanup pass: removed the execution metadata output card, removed visible source/data-key pill noise from output card headers, and removed visible `//` styling from the Factors V2 UI.

---

I'll give you the full engineering breakdown for every checked feature, maxed out, with computation logic, UI code snippets integrated into your existing component architecture, and Bloomberg-level output quality specifications. I'll go feature by feature, section by section.

---

## FEATURE 1: Factor Valuation Spread Monitor

### Computation Logic

**Step 1: Universe Partition**

At each date T, sort all N stocks by factor score. Long book = top quintile (ranks 1 to N/5). Short book = bottom quintile (ranks 4N/5 to N).

**Step 2: Characteristic Spread**

For each factor, compute the value-weighted mean of the underlying fundamental characteristic for the long book minus the short book:

```
spread(T) = VW_mean_char(long_book, T) - VW_mean_char(short_book, T)
```

Factor-to-characteristic mapping:
- Value: P/B spread, E/P spread, EV/EBITDA spread (sign-inverted so higher spread = cheaper value)
- Momentum: trailing 12M-1M return spread
- Quality: ROE spread, gross profitability spread
- Low-Vol: realized 60-day volatility spread (inverted)
- Size: log market cap spread

**Step 3: Historical Percentile**

For each date T, compute:

```
pct(T) = ECDF(spread(T-lookback:T-1))[spread(T)] * 100
```

where ECDF is the empirical CDF of historical spread values over the chosen lookback window (756, 1260, or 2520 trading days for 3/5/10 years).

**Step 4: Multi-Factor Dashboard**

Run steps 1-3 simultaneously for all selected factors. Output a cross-sectional vector of current percentiles. Percentile below 30 = historically cheap long book (high expected return). Above 70 = stretched.

**Step 5: Expected Return Regression**

For each factor, regress subsequent H-day factor return on contemporaneous spread percentile:

```
ret(T, T+H) = alpha + beta * pct(T) + epsilon
```

Estimate via OLS on full history. At current pct_now, implied return = alpha + beta * pct_now. Report with 90% prediction interval from residual standard error.

**Step 6: Valuation Correlation Matrix**

Compute the rolling 252-day Pearson correlation matrix of the daily percentile series across all K selected factors. This gives a K x K matrix showing which factors are simultaneously cheap or stretched.

**Step 7: Cross-Sector Decomposition**

For each GICS sector S, compute within-sector spread:

```
spread_sector(S, T) = VW_mean_char(long_book ∩ sector_S, T) - VW_mean_char(short_book ∩ sector_S, T)
```

Weight by sector's share of long book by market cap. This shows whether the aggregate spread is concentrated in one sector or pervasive.

**Step 8: Alert System**

At every run, compare current pct_now to user-set thresholds. If pct_now > threshold_high or pct_now < threshold_low for any factor, push to alerts array in response and trigger in-UI notification badge. Store in IndexedDB keyed by factor + date for lifecycle tracking (open, acknowledged, resolved).

**Step 9: Historical Crisis Anchors**

Precompute spread percentile levels at: GFC peak (2008-09-15), COVID crash (2020-03-16), rate shock (2022-10-03), Liberation Day (2025-04-02). Attach as reference annotations on the time series chart.

---

### Multi-Factor Simultaneous Dashboard: All Factors Side by Side

The dashboard output uses the `summaryGauges` chart type, but extended with a custom layout for 8+ factors simultaneously. The key addition is the **valuation correlation matrix** as a default output and the **cross-sector contribution table** below each gauge.

**Section definitions for F01:**

```javascript
// In your F01 registry entry, sections array:

const f01Sections = [
  {
    id: "f01-gauge-panel",
    title: "Live Factor Valuation Gauges",
    dataKey: "gauge_panel",
    source: "charts",
    chartType: "multiFactorGaugePanel",
    rank: "primary",
    description: "Real-time percentile dial for every selected factor. Green = historically cheap, Red = stretched.",
  },
  {
    id: "f01-percentile-series",
    title: "Historical Percentile Time Series",
    dataKey: "percentile_series",
    source: "charts",
    chartType: "area",
    config: {
      colorBySign: false,
      referenceLines: [
        { value: 70, stroke: "#EF4444", strokeDasharray: "5 4", label: "Stretched" },
        { value: 30, stroke: "#22C55E", strokeDasharray: "5 4", label: "Cheap" },
      ],
      referenceAreas: [
        { y1: 70, y2: 100, fill: "#EF4444", fillOpacity: 0.06 },
        { y1: 0, y2: 30, fill: "#22C55E", fillOpacity: 0.06 },
      ],
    },
  },
  {
    id: "f01-implied-return",
    title: "Implied 12M Expected Return vs Spread Percentile",
    dataKey: "implied_return",
    source: "charts",
    chartType: "scatter",
    config: { xKey: "percentile", yKeys: ["implied_return_pct"], colorBySign: false },
  },
  {
    id: "f01-valuation-corr-matrix",
    title: "Factor Valuation Correlation Matrix",
    dataKey: "valuation_correlation_matrix",
    source: "charts",
    chartType: "heatmap",
    config: { palette: "diverging" },
  },
  {
    id: "f01-cross-sector-table",
    title: "Cross-Sector Valuation Spread Decomposition",
    dataKey: "cross_sector_table",
    source: "tables",
    chartType: "table",
    config: { colorBySign: true },
  },
  {
    id: "f01-crisis-anchor-table",
    title: "Factor Valuation History at Crisis Dates",
    dataKey: "crisis_anchor_table",
    source: "tables",
    chartType: "table",
    config: { colorByThreshold: false },
  },
  {
    id: "f01-alert-feed",
    title: "Live Alert Feed",
    dataKey: "alert_feed",
    source: "alerts",
    chartType: "alertFeed",
  },
];
```

**Multi-Factor Gauge Panel Component:**

This is a new chart type not in your existing `RenderFeatureSection`. Add the `multiFactorGaugePanel` case and the component:

```javascript
// Add to RenderFeatureSection switch block:
if (section.chartType === "multiFactorGaugePanel") return <MultiFactorGaugePanel data={data} config={section.config} />;

// Component:
function MultiFactorGaugePanel({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ factor: "value_pb", label: "Value P/B", percentile: 82.3, implied_return: -1.4, delta_1m: 3.2, status: "stretched" }, ...]

  const sorted = useMemo(() =>
    [...rows].sort((a, b) => (numberLike(b.percentile) ?? 0) - (numberLike(a.percentile) ?? 0)),
  [rows]);

  return (
    <div className="mfg-panel">
      {/* Summary strip: most stretched and most cheap */}
      <div className="mfg-extremes">
        <div className="mfg-extreme-card red">
          <span>Most Stretched</span>
          <strong>{titleize(sorted[0]?.label || sorted[0]?.factor || "—")}</strong>
          <b className="mono">{formatValue(sorted[0]?.percentile)}th pct</b>
        </div>
        <div className="mfg-extreme-card green">
          <span>Most Attractive</span>
          <strong>{titleize(sorted[sorted.length - 1]?.label || sorted[sorted.length - 1]?.factor || "—")}</strong>
          <b className="mono">{formatValue(sorted[sorted.length - 1]?.percentile)}th pct</b>
        </div>
      </div>

      {/* Factor grid */}
      <div className="mfg-grid">
        {rows.map((row) => {
          const pct = numberLike(row.percentile) ?? 50;
          const bounded = Math.max(0, Math.min(100, pct));
          const status = bounded >= 70 ? "stretched" : bounded <= 30 ? "cheap" : "neutral";
          const color = status === "stretched" ? TOKENS.red : status === "cheap" ? TOKENS.green : TOKENS.amber;
          const impliedRet = numberLike(row.implied_return ?? row.implied_return_pct);
          const delta = numberLike(row.delta_1m ?? row.delta);

          return (
            <div className={`mfg-card status-${status}`} key={row.factor || row.label}>
              {/* Mini horizontal gauge bar */}
              <div className="mfg-bar-track">
                <div className="mfg-bar-fill" style={{ width: `${bounded}%`, background: color }} />
                {/* Threshold markers */}
                <div className="mfg-threshold" style={{ left: "30%" }} />
                <div className="mfg-threshold" style={{ left: "70%" }} />
              </div>

              <div className="mfg-card-body">
                <div className="mfg-factor-name">{titleize(row.label || row.factor)}</div>
                <div className="mfg-pct mono" style={{ color }}>{bounded.toFixed(1)}<sup>th</sup></div>
                {impliedRet != null ? (
                  <div className={`mfg-implied mono ${impliedRet >= 0 ? "positive" : "negative"}`}>
                    {impliedRet >= 0 ? "+" : ""}{impliedRet.toFixed(1)}% implied 12M
                  </div>
                ) : null}
                {delta != null ? (
                  <div className="mfg-delta">
                    <DeltaLabel delta={delta} positiveDirection={status === "cheap" ? "down" : "up"} />
                    <small>1M chg</small>
                  </div>
                ) : null}
                {/* Micro sparkline for this factor's 90-day percentile trail */}
                <Sparkline value={bounded} index={rows.indexOf(row)} />
              </div>

              {/* Status badge */}
              <div className="mfg-badge" style={{ background: color }}>
                {status.toUpperCase()}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**CSS additions for multi-factor gauge panel:**

```javascript
// Append to your styles string:
const f01Styles = `
  .mfg-panel { display: grid; gap: 18px; }
  .mfg-extremes { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .mfg-extreme-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 14px 16px; display: grid; gap: 4px; }
  .mfg-extreme-card.red { border-color: rgba(239,68,68,.36); background: rgba(239,68,68,.07); }
  .mfg-extreme-card.green { border-color: rgba(34,197,94,.36); background: rgba(34,197,94,.07); }
  .mfg-extreme-card span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .mfg-extreme-card strong { font-size: 18px; color: ${TOKENS.text}; }
  .mfg-extreme-card b { font-size: 13px; }
  .mfg-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
  .mfg-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 12px; display: grid; gap: 8px; position: relative; overflow: hidden; transition: border-color .15s ease; }
  .mfg-card.status-stretched { border-color: rgba(239,68,68,.32); }
  .mfg-card.status-cheap { border-color: rgba(34,197,94,.32); }
  .mfg-card:hover { border-color: rgba(245,164,0,.4); }
  .mfg-bar-track { height: 6px; background: ${TOKENS.active}; border-radius: 999px; position: relative; overflow: visible; }
  .mfg-bar-fill { height: 100%; border-radius: 999px; transition: width .6s cubic-bezier(.4,0,.2,1); }
  .mfg-threshold { position: absolute; top: -3px; width: 1px; height: 12px; background: ${TOKENS.borderSubtle}; }
  .mfg-card-body { display: grid; gap: 4px; }
  .mfg-factor-name { color: ${TOKENS.text}; font-size: 12px; font-weight: 700; }
  .mfg-pct { font-size: 26px; font-weight: 800; line-height: 1; }
  .mfg-pct sup { font-size: 12px; vertical-align: super; }
  .mfg-implied { font-size: 11px; }
  .mfg-delta { display: flex; align-items: center; gap: 6px; }
  .mfg-delta small { color: ${TOKENS.muted}; font-size: 10px; }
  .mfg-badge { position: absolute; top: 8px; right: 8px; color: ${TOKENS.panel}; font-size: 8px; font-weight: 900; letter-spacing: .14em; border-radius: 3px; padding: 3px 5px; }
`;
```

**Alert Feed Component:**

```javascript
function AlertFeed({ data }) {
  const alerts = useMemo(() => rowsFrom(data), [data]);
  const [filter, setFilter] = useState("ALL");
  const visible = filter === "ALL" ? alerts : alerts.filter((a) => a.status === filter.toLowerCase());

  return (
    <div className="alert-feed">
      <div className="alert-feed-header">
        <span className="alert-feed-count">{alerts.filter((a) => !a.resolved).length} open</span>
        <div className="alert-feed-filters">
          {["ALL", "OPEN", "TRIGGERED", "RESOLVED"].map((f) => (
            <button
              key={f}
              className={filter === f ? "active" : ""}
              onClick={() => setFilter(f)}
              type="button"
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="alert-list">
        {visible.map((alert, i) => {
          const pct = numberLike(alert.percentile ?? alert.current_pct);
          const color = pct >= 70 ? TOKENS.red : pct <= 30 ? TOKENS.green : TOKENS.amber;
          return (
            <div className={`alert-row ${alert.resolved ? "resolved" : "open"}`} key={i}>
              <i className="alert-dot" style={{ background: color }} />
              <div className="alert-content">
                <strong>{titleize(alert.factor || alert.label)}</strong>
                <span>{alert.message || `Crossed ${alert.threshold}th percentile threshold`}</span>
                <div className="alert-meta">
                  <b className="mono" style={{ color }}>{formatValue(pct)}th pct</b>
                  <small>{alert.triggered_at || alert.date}</small>
                  {alert.resolved ? <em className="resolved-badge">RESOLVED</em> : null}
                </div>
              </div>
            </div>
          );
        })}
        {!visible.length ? (
          <div className="alert-empty">No alerts match this filter. Thresholds are checked on every run.</div>
        ) : null}
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "alertFeed") return <AlertFeed data={data} />;
```

Alert feed CSS:

```javascript
const alertFeedStyles = `
  .alert-feed { display: grid; gap: 10px; }
  .alert-feed-header { display: flex; align-items: center; gap: 14px; }
  .alert-feed-count { color: ${TOKENS.amber}; font-family: "Quant360 Mono","JetBrains Mono",monospace; font-size: 11px; font-weight: 800; }
  .alert-feed-filters { display: flex; gap: 6px; }
  .alert-feed-filters button { height: 24px; padding: 0 8px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 4px; font-size: 9px; font-weight: 800; letter-spacing: .1em; cursor: pointer; }
  .alert-feed-filters button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.08); }
  .alert-list { display: grid; gap: 8px; }
  .alert-row { display: grid; grid-template-columns: 10px 1fr; gap: 10px; align-items: start; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 10px 12px; }
  .alert-row.resolved { opacity: .55; }
  .alert-dot { width: 8px; height: 8px; border-radius: 999px; margin-top: 4px; flex-shrink: 0; }
  .alert-content { display: grid; gap: 3px; }
  .alert-content strong { color: ${TOKENS.text}; font-size: 13px; }
  .alert-content span { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.4; }
  .alert-meta { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
  .alert-meta small { color: ${TOKENS.muted}; font-size: 10px; }
  .resolved-badge { color: ${TOKENS.green}; font-size: 9px; font-weight: 800; letter-spacing: .1em; border: 1px solid rgba(34,197,94,.3); border-radius: 3px; padding: 1px 5px; font-style: normal; }
  .alert-empty { color: ${TOKENS.muted}; font-size: 12px; padding: 16px; border: 1px dashed ${TOKENS.border}; border-radius: 7px; }
`;
```

**Historical Percentile Time Series with Crisis Annotations:**

The existing `StandardChart` with `area` type handles the base. The crisis annotations are injected as `referenceLines` with labels. The backend should return the percentile time series and a separate `crisis_anchors` array. The section config then injects them:

```javascript
// In your section config for the percentile series:
{
  id: "f01-percentile-series",
  title: "Historical Valuation Spread Percentile — 10Y",
  dataKey: "percentile_series",
  source: "charts",
  chartType: "annotatedTimeSeries",  // new chart type below
  config: {
    crisisDataKey: "crisis_anchors",  // parallel key in response
    thresholdLines: [
      { value: 70, color: TOKENS.red, label: "Stretched" },
      { value: 30, color: TOKENS.green, label: "Cheap" },
    ],
    fillAbove70: true,
    fillBelow30: true,
  },
}
```

**AnnotatedTimeSeries component:**

```javascript
function AnnotatedTimeSeries({ response, section }) {
  const rows = useMemo(() => rowsFrom(pickData(response, section)), [response, section]);
  const crisisAnchors = useMemo(
    () => rowsFrom(response?.charts?.[section.config?.crisisDataKey] || []),
    [response, section]
  );
  const { xKey, yKeys } = useMemo(() => inferKeys(rows, section.config), [rows, section.config]);

  if (!rows.length) return <EmptySection response={response} section={section} />;

  const yValues = rows.flatMap((r) => yKeys.map((k) => numberLike(r[k])).filter((v) => v != null));
  const yMin = 0;
  const yMax = 100;

  return (
    <div className="annotated-ts">
      <ResponsiveContainer height={420} width="100%">
        <AreaChart data={rows} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <defs>
            {yKeys.map((key, i) => (
              <linearGradient key={key} id={`ats-grad-${key}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.28} />
                <stop offset="100%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.02} />
              </linearGradient>
            ))}
            {/* Crisis band fill above 70 */}
            <linearGradient id="ats-red-zone" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={TOKENS.red} stopOpacity={0.18} />
              <stop offset="100%" stopColor={TOKENS.red} stopOpacity={0.04} />
            </linearGradient>
            <linearGradient id="ats-green-zone" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={TOKENS.green} stopOpacity={0.04} />
              <stop offset="100%" stopColor={TOKENS.green} stopOpacity={0.14} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} />
          <YAxis domain={[0, 100]} {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          {/* Regime zones */}
          <ReferenceArea y1={70} y2={100} fill="url(#ats-red-zone)" fillOpacity={1} />
          <ReferenceArea y1={0} y2={30} fill="url(#ats-green-zone)" fillOpacity={1} />
          {/* Threshold lines */}
          <ReferenceLine y={70} stroke={TOKENS.red} strokeDasharray="4 4" strokeOpacity={0.7} label={{ value: "Stretched", fill: TOKENS.red, fontSize: 10, position: "insideTopRight" }} />
          <ReferenceLine y={30} stroke={TOKENS.green} strokeDasharray="4 4" strokeOpacity={0.7} label={{ value: "Cheap", fill: TOKENS.green, fontSize: 10, position: "insideBottomRight" }} />
          {/* Crisis event markers */}
          {crisisAnchors.map((anchor, i) => (
            <ReferenceLine
              key={i}
              x={anchor.date || anchor.x}
              stroke={TOKENS.amber}
              strokeDasharray="3 5"
              strokeOpacity={0.65}
              label={{ value: anchor.label || anchor.event, fill: TOKENS.amber, fontSize: 9, angle: -90, position: "insideTopLeft", offset: 4 }}
            />
          ))}
          {yKeys.map((key, i) => (
            <Area
              key={key}
              dataKey={key}
              stroke={SERIES[i % SERIES.length]}
              strokeWidth={2}
              fill={`url(#ats-grad-${key})`}
              type="monotone"
              dot={false}
            />
          ))}
          {rows.length > 20 && <Brush dataKey={xKey} fill={TOKENS.elevated} height={28} stroke={TOKENS.border} />}
        </AreaChart>
      </ResponsiveContainer>
      {/* Crisis anchor legend below chart */}
      {crisisAnchors.length ? (
        <div className="crisis-legend">
          {crisisAnchors.map((anchor, i) => (
            <div key={i} className="crisis-chip">
              <i />
              <span>{anchor.label || anchor.event}</span>
              <b className="mono">{anchor.date}</b>
              {anchor.percentile != null ? <em style={{ color: numberLike(anchor.percentile) >= 70 ? TOKENS.red : TOKENS.green }}>{formatValue(anchor.percentile)}th pct</em> : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "annotatedTimeSeries") return <AnnotatedTimeSeries response={response} section={section} />;
```

CSS:

```javascript
const annotatedTsStyles = `
  .annotated-ts { display: grid; gap: 14px; }
  .crisis-legend { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 8px; border-top: 1px solid ${TOKENS.borderSubtle}; }
  .crisis-chip { display: flex; align-items: center; gap: 6px; border: 1px solid rgba(245,164,0,.24); background: rgba(245,164,0,.06); border-radius: 5px; padding: 5px 9px; }
  .crisis-chip i { width: 6px; height: 6px; border-radius: 999px; background: ${TOKENS.amber}; flex-shrink: 0; }
  .crisis-chip span { color: ${TOKENS.secondary}; font-size: 10px; }
  .crisis-chip b { font-size: 10px; color: ${TOKENS.text}; }
  .crisis-chip em { font-size: 10px; font-style: normal; font-family: "Quant360 Mono","JetBrains Mono",monospace; }
`;
```

---

## FEATURE 2: Portfolio X-Ray — Animated Rolling Exposure Heatmap and Multi-Portfolio Comparison

### Computation Logic

**Step 1: Characteristic-Based Exposures**

For each stock i in the portfolio, compute standardized characteristic z-scores relative to the full universe cross-section at date T:

```
z_factor_i(T) = (char_i(T) - mean_universe(char, T)) / std_universe(char, T)
```

Portfolio-level exposure for factor F:

```
exp_F(T) = sum_i [ w_i(T) * z_F_i(T) ]
```

Active exposure:

```
active_exp_F(T) = exp_F_portfolio(T) - exp_F_benchmark(T)
```

**Step 2: Return-Based Exposures**

For each stock i, run time-series OLS over the estimation window [T-W, T]:

```
r_i(t) = alpha_i + sum_F [beta_F_i * f_F(t)] + epsilon_i(t)
```

Portfolio-level return-based exposure:

```
beta_F_portfolio(T) = sum_i [ w_i(T) * beta_F_i(T) ]
```

**Step 3: Rolling Exposure Time Series**

At each monthly rebalancing date T_k, repeat steps 1 and 2. This produces a time series of length K for each factor's exposure. Store as a matrix (K months x F factors).

**Step 4: Divergence Detection**

For each factor F and each stock i, divergence flag:

```
diverge_i_F = |z_F_i_characteristic - beta_F_i_return_based| > 0.3
```

**Step 5: Exposure Budget**

Total portfolio tracking error from factor covariance matrix Sigma:

```
TE = sqrt(w_active' * Sigma_F * w_active)
```

Factor contribution to TE for factor F:

```
contrib_F = w_active_F * (Sigma_F * w_active)_F / TE
```

---

### Animated Rolling Exposure Heatmap

This uses a CSS-animation-based approach over the static snapshot series, since DCC-GARCH live heatmap is not a realtime default. The backend returns a `rolling_exposure_snapshots` array of monthly matrices. The frontend animates through them.

```javascript
function RollingExposureHeatmap({ data, config = {} }) {
  const snapshots = useMemo(() => {
    if (Array.isArray(data?.snapshots)) return data.snapshots;
    // Fallback: treat data itself as a single snapshot
    return [data];
  }, [data]);

  const [frame, setFrame] = useState(snapshots.length - 1);
  const [playing, setPlaying] = useState(false);
  const rafRef = useRef(null);
  const lastRef = useRef(null);
  const FRAME_MS = config.frameDurationMs ?? 280;

  useEffect(() => {
    if (!playing) {
      cancelAnimationFrame(rafRef.current);
      return undefined;
    }
    function tick(now) {
      if (!lastRef.current || now - lastRef.current >= FRAME_MS) {
        lastRef.current = now;
        setFrame((f) => {
          if (f >= snapshots.length - 1) { setPlaying(false); return f; }
          return f + 1;
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [playing, snapshots.length, FRAME_MS]);

  const current = snapshots[frame] ?? snapshots[snapshots.length - 1];
  const date = current?.date ?? current?.as_of ?? `Snapshot ${frame + 1}`;

  return (
    <div className="rolling-heatmap">
      {/* Playback controls */}
      <div className="rolling-controls">
        <button onClick={() => { setFrame(0); setPlaying(false); }} type="button" title="Reset">⏮</button>
        <button onClick={() => setFrame((f) => Math.max(0, f - 1))} type="button" title="Step back">◀</button>
        <button
          className={playing ? "active" : ""}
          onClick={() => {
            if (frame >= snapshots.length - 1) setFrame(0);
            setPlaying((p) => !p);
          }}
          type="button"
          title={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <button onClick={() => setFrame((f) => Math.min(snapshots.length - 1, f + 1))} type="button" title="Step forward">▶</button>
        <button onClick={() => { setFrame(snapshots.length - 1); setPlaying(false); }} type="button" title="Jump to latest">⏭</button>
        <div className="rolling-scrubber">
          <input
            type="range"
            min={0}
            max={snapshots.length - 1}
            value={frame}
            onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }}
          />
        </div>
        <span className="rolling-date mono">{date}</span>
        <span className="rolling-count mono">{frame + 1}/{snapshots.length}</span>
      </div>
      {/* Heatmap for current frame */}
      <Heatmap data={current?.matrix ?? current} config={{ ...config, animated: false }} />
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "rollingHeatmap") return <RollingExposureHeatmap data={data} config={section.config} />;
```

CSS:

```javascript
const rollingHeatmapStyles = `
  .rolling-heatmap { display: grid; gap: 10px; }
  .rolling-controls { display: flex; align-items: center; gap: 8px; padding: 8px; background: ${TOKENS.elevated}; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 7px; }
  .rolling-controls button { width: 28px; height: 28px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.secondary}; border-radius: 5px; cursor: pointer; font-size: 12px; display: grid; place-items: center; }
  .rolling-controls button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.08); }
  .rolling-scrubber { flex: 1; }
  .rolling-scrubber input[type="range"] { width: 100%; accent-color: ${TOKENS.accent}; }
  .rolling-date { color: ${TOKENS.text}; font-size: 11px; white-space: nowrap; }
  .rolling-count { color: ${TOKENS.muted}; font-size: 10px; }
`;
```

**Multi-Portfolio Side-by-Side Comparison:**

The existing `splitMode` in your `CustomFeaturePage` handles two portfolios. For F02, extend this to support up to three portfolios with a tab-and-overlay layout:

```javascript
function MultiPortfolioCompare({ sections, responses, labels }) {
  const [activePort, setActivePort] = useState(0);
  const [overlayMode, setOverlayMode] = useState(false);

  return (
    <div className="multi-port-compare">
      {/* Tab bar */}
      <div className="port-tabs">
        {labels.map((label, i) => (
          <button
            key={i}
            className={activePort === i ? "active" : ""}
            onClick={() => setActivePort(i)}
            type="button"
          >
            <i style={{ background: SERIES[i % SERIES.length] }} />
            {label || `Portfolio ${i + 1}`}
          </button>
        ))}
        <button
          className={`overlay-toggle ${overlayMode ? "active" : ""}`}
          onClick={() => setOverlayMode((m) => !m)}
          type="button"
          title="Overlay all portfolios on same chart"
        >
          Overlay
        </button>
      </div>

      {overlayMode ? (
        /* Overlay: merge all portfolio exposure data onto one chart */
        <OverlayExposureChart responses={responses} labels={labels} />
      ) : (
        /* Single portfolio display */
        <div className="port-single">
          {sections.map((section) => (
            <AnnotatedOutputCard
              key={`port-${activePort}-${section.id}`}
              section={{ ...section, id: `port-${activePort}-${section.id}` }}
              cardData={pickData(responses[activePort], section)}
              loading={!responses[activePort]}
              annotationMode={null}
              fullScreenId={null}
              isActive={false}
              onAddAnnotation={() => {}}
              onDrill={() => {}}
              onResolve={() => {}}
              onToggleAnnotationMode={() => {}}
              onToggleFullscreen={() => {}}
              previousCardData={null}
              sectionAnnotations={[]}
              sections={sections}
            >
              <RenderFeatureSection response={responses[activePort]} section={section} />
            </AnnotatedOutputCard>
          ))}
        </div>
      )}
    </div>
  );
}

function OverlayExposureChart({ responses, labels }) {
  // Merge factor exposure bars from all portfolios into one grouped bar chart
  const combined = useMemo(() => {
    const allFactors = new Set();
    responses.forEach((resp) => {
      const rows = rowsFrom(resp?.charts?.exposure_bars);
      rows.forEach((r) => allFactors.add(r.factor || r.name));
    });
    return [...allFactors].map((factor) => {
      const row = { factor: titleize(factor) };
      responses.forEach((resp, i) => {
        const rows = rowsFrom(resp?.charts?.exposure_bars);
        const match = rows.find((r) => (r.factor || r.name) === factor);
        row[labels[i] || `P${i + 1}`] = numberLike(match?.exposure ?? match?.value) ?? 0;
      });
      return row;
    });
  }, [responses, labels]);

  return (
    <div className="overlay-chart">
      <StandardChart
        data={combined}
        type="bar"
        config={{
          xKey: "factor",
          yKeys: labels.map((l, i) => l || `P${i + 1}`),
          seriesColors: SERIES,
          colorBySign: false,
          referenceLines: [{ value: 0, stroke: TOKENS.secondary, strokeDasharray: "2 4" }],
        }}
      />
    </div>
  );
}
```

CSS:

```javascript
const multiPortStyles = `
  .multi-port-compare { display: grid; gap: 12px; }
  .port-tabs { display: flex; gap: 6px; align-items: center; border-bottom: 1px solid ${TOKENS.borderSubtle}; padding-bottom: 10px; flex-wrap: wrap; }
  .port-tabs button { height: 30px; padding: 0 12px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 5px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 7px; }
  .port-tabs button.active { color: ${TOKENS.text}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.08); }
  .port-tabs button i { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
  .overlay-toggle { margin-left: auto; color: ${TOKENS.secondary} !important; }
  .overlay-toggle.active { color: ${TOKENS.amber} !important; }
  .port-single { display: grid; gap: 10px; }
  .overlay-chart { border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 12px; background: ${TOKENS.elevated}; }
`;
```

**Active Return Waterfall vs Benchmark — Separate Premium Output:**

The backend returns a `waterfall_active_vs_benchmark` dataset with rows shaped as `[{ name, allocation_effect, selection_effect, interaction_effect, total }]` per sector. The existing `Waterfall` component handles the visual, but you need a stacked variant that shows the three sub-effects per component. Add:

```javascript
function StackedAttributionWaterfall({ data }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  if (!rows.length) return <EmptySection section={{ dataKey: "attribution_waterfall" }} />;

  // Find all effect keys (allocation, selection, interaction, total)
  const effectKeys = ["allocation_effect", "selection_effect", "interaction_effect"];
  const hasAllKeys = effectKeys.every((k) => rows.some((r) => numberLike(r[k]) != null));

  if (!hasAllKeys) return <Waterfall data={data} />;

  const chartData = rows.map((r) => ({
    name: titleize(r.name || r.sector || r.component || ""),
    allocation: numberLike(r.allocation_effect) ?? 0,
    selection: numberLike(r.selection_effect) ?? 0,
    interaction: numberLike(r.interaction_effect) ?? 0,
    total: numberLike(r.total ?? r.active_return) ?? 0,
  }));

  return (
    <div className="attribution-waterfall">
      <div className="attribution-legend">
        {[["Allocation", TOKENS.teal], ["Selection", TOKENS.accent], ["Interaction", TOKENS.purple]].map(([label, color]) => (
          <div key={label} className="attr-legend-item">
            <i style={{ background: color }} />
            <span>{label}</span>
          </div>
        ))}
      </div>
      <ResponsiveContainer height={420} width="100%">
        <BarChart data={chartData} margin={{ top: 14, right: 26, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="name" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeOpacity={0.7} />
          <Bar dataKey="allocation" stackId="stack" fill={TOKENS.teal} />
          <Bar dataKey="selection" stackId="stack" fill={TOKENS.accent} />
          <Bar dataKey="interaction" stackId="stack" fill={TOKENS.purple} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {/* Summary totals row */}
      <div className="attribution-totals">
        {["allocation", "selection", "interaction"].map((key) => {
          const total = chartData.reduce((s, r) => s + (r[key] ?? 0), 0);
          return (
            <div key={key} className="attr-total-card">
              <span>{titleize(key)}</span>
              <b className={`mono ${total >= 0 ? "positive" : "negative"}`}>
                {total >= 0 ? "+" : ""}{(total * 100).toFixed(2)} bps
              </b>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "attributionWaterfall") return <StackedAttributionWaterfall data={data} />;
```

CSS:

```javascript
const attrWaterfallStyles = `
  .attribution-waterfall { display: grid; gap: 14px; }
  .attribution-legend { display: flex; gap: 14px; align-items: center; }
  .attr-legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: ${TOKENS.secondary}; }
  .attr-legend-item i { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .attribution-totals { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .attr-total-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 10px 12px; }
  .attr-total-card span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; display: block; margin-bottom: 4px; }
  .attr-total-card b { font-size: 16px; }
`;
```

**Decision Freshness Score:**

This is an output card within F03. The backend returns per-holding freshness scores. Render as a horizontal gauge + ranked table:

```javascript
function DecisionFreshnessScore({ data }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const aggregate = useMemo(() => {
    const scores = rows.map((r) => numberLike(r.freshness_score ?? r.carryover_pct ?? r.value)).filter((v) => v != null);
    if (!scores.length) return null;
    return scores.reduce((s, v) => s + v, 0) / scores.length;
  }, [rows]);

  return (
    <div className="freshness-panel">
      {/* Aggregate score gauge */}
      {aggregate != null ? (
        <div className="freshness-agg">
          <span>Portfolio Decision Freshness</span>
          <div className="freshness-bar-track">
            <div
              className="freshness-bar-fill"
              style={{
                width: `${Math.max(0, Math.min(100, aggregate))}%`,
                background: aggregate >= 70 ? TOKENS.green : aggregate >= 40 ? TOKENS.amber : TOKENS.red,
              }}
            />
          </div>
          <b className="mono">{aggregate.toFixed(1)}%</b>
          <small>
            {aggregate >= 70
              ? "Current-period decisions dominate P&L — high decision freshness"
              : aggregate >= 40
              ? "Mix of current and carryover decisions — moderate freshness"
              : "Carryover from prior periods dominates — decisions may be stale"}
          </small>
        </div>
      ) : null}

      {/* Per-holding breakdown */}
      <DataTable
        data={rows}
        config={{
          colorBySign: false,
          colorByIntensity: false,
        }}
      />
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "freshnessScore") return <DecisionFreshnessScore data={data} />;
```

CSS:

```javascript
const freshnessStyles = `
  .freshness-panel { display: grid; gap: 14px; }
  .freshness-agg { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 14px 16px; display: grid; gap: 8px; }
  .freshness-agg span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .freshness-bar-track { height: 10px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; }
  .freshness-bar-fill { height: 100%; border-radius: 999px; transition: width .6s cubic-bezier(.4,0,.2,1); }
  .freshness-agg b { font-size: 28px; font-family: "Quant360 Mono","JetBrains Mono",monospace; }
  .freshness-agg small { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.45; }
`;
```

---

## FEATURE 4: Regime Analysis — 30D/90D Trend Display and Regime Sensitivity Table

### Computation Logic

**Probabilistic Regime Timeline:**

At each date T, the HMM outputs a probability vector P(T) = [p1(T), p2(T), ..., pK(T)] where K is the number of states. The composite probability for state k at time T is:

```
composite_k(T) = w_HMM * p_HMM_k(T) + w_rules * p_rules_k(T) + w_GMM * p_GMM_k(T)
```

Weights are updated by rolling log-loss of each model over the prior 63 trading days.

**30D/90D Trend:**

Compute the rolling 30-day and 90-day change in each state's probability:

```
trend_k_30D(T) = composite_k(T) - composite_k(T - 30)
trend_k_90D(T) = composite_k(T) - composite_k(T - 90)
```

**Regime Sensitivity Table:**

For a given portfolio P with factor exposures E(F) from F02, and regime-conditional factor returns mu_k(F) from the conditional return heatmap:

```
expected_return_k = sum_F [ E(F) * mu_k(F) ]
```

Compute for each of K regime states. This gives the portfolio's expected return in each regime.

---

**30D/90D Current Regime Trend Component:**

```javascript
function RegimeTrendPanel({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ state: "Expansion", prob_now: 0.62, prob_30d_ago: 0.48, prob_90d_ago: 0.55, color: "#22C55E" }, ...]

  return (
    <div className="regime-trend-panel">
      {/* Stacked probability bar: current */}
      <div className="regime-stack-label">Current Regime Probability</div>
      <div className="regime-stack-bar">
        {rows.map((row, i) => {
          const prob = numberLike(row.prob_now ?? row.probability ?? row.value) ?? 0;
          const color = row.color || SERIES[i % SERIES.length];
          return (
            <div
              key={row.state || i}
              className="regime-stack-segment"
              style={{ width: `${prob * 100}%`, background: color }}
              title={`${titleize(row.state)}: ${(prob * 100).toFixed(1)}%`}
            />
          );
        })}
      </div>

      {/* Per-state trend rows */}
      <div className="regime-trend-rows">
        {rows.map((row, i) => {
          const probNow = numberLike(row.prob_now ?? row.probability) ?? 0;
          const prob30 = numberLike(row.prob_30d_ago) ?? probNow;
          const prob90 = numberLike(row.prob_90d_ago) ?? probNow;
          const delta30 = probNow - prob30;
          const delta90 = probNow - prob90;
          const color = row.color || SERIES[i % SERIES.length];

          return (
            <div className="regime-trend-row" key={row.state || i}>
              <div className="regime-state-name">
                <i style={{ background: color }} />
                <span>{titleize(row.state || `State ${i + 1}`)}</span>
              </div>
              <div className="regime-prob-now mono" style={{ color }}>
                {(probNow * 100).toFixed(1)}%
              </div>
              <div className={`regime-delta mono ${delta30 >= 0 ? "positive" : "negative"}`}>
                {delta30 >= 0 ? "+" : ""}{(delta30 * 100).toFixed(1)}pp
                <small>30D</small>
              </div>
              <div className={`regime-delta mono ${delta90 >= 0 ? "positive" : "negative"}`}>
                {delta90 >= 0 ? "+" : ""}{(delta90 * 100).toFixed(1)}pp
                <small>90D</small>
              </div>
              {/* Mini trend line */}
              <div className="regime-mini-trend">
                <svg viewBox="0 0 80 24" width="80" height="24">
                  <line x1="0" y1={24 - prob90 * 24} x2="40" y2={24 - prob30 * 24} stroke={color} strokeWidth="2" strokeLinecap="round" />
                  <line x1="40" y1={24 - prob30 * 24} x2="80" y2={24 - probNow * 24} stroke={color} strokeWidth="2" strokeLinecap="round" />
                  <circle cx="80" cy={24 - probNow * 24} r="3" fill={color} />
                </svg>
              </div>
            </div>
          );
        })}
      </div>

      {/* Trend interpretation */}
      <div className="regime-interpretation">
        {rows.map((row, i) => {
          const prob = numberLike(row.prob_now ?? row.probability) ?? 0;
          const delta30 = prob - (numberLike(row.prob_30d_ago) ?? prob);
          if (Math.abs(delta30) < 0.05) return null;
          const direction = delta30 > 0 ? "rising" : "falling";
          return (
            <div key={i} className="regime-interp-line">
              <i style={{ background: row.color || SERIES[i % SERIES.length] }} />
              <span>
                {titleize(row.state)} probability is <b>{direction}</b> (+{Math.abs(delta30 * 100).toFixed(0)}pp over 30D)
                {direction === "rising" && prob > 0.5 ? " — dominant regime, high confidence in factor conditional returns" : ""}
                {direction === "falling" && prob < 0.2 ? " — regime exit signal, reduce reliance on this regime's conditional return forecasts" : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "regimeTrend") return <RegimeTrendPanel data={data} config={section.config} />;
```

CSS:

```javascript
const regimeTrendStyles = `
  .regime-trend-panel { display: grid; gap: 14px; }
  .regime-stack-label { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .14em; font-weight: 800; }
  .regime-stack-bar { display: flex; height: 12px; border-radius: 999px; overflow: hidden; gap: 1px; }
  .regime-stack-segment { height: 100%; transition: width .5s cubic-bezier(.4,0,.2,1); }
  .regime-trend-rows { display: grid; gap: 8px; }
  .regime-trend-row { display: grid; grid-template-columns: 180px 80px 100px 100px 90px; gap: 10px; align-items: center; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 10px 12px; }
  .regime-state-name { display: flex; align-items: center; gap: 8px; }
  .regime-state-name i { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
  .regime-state-name span { font-size: 12px; color: ${TOKENS.text}; font-weight: 600; }
  .regime-prob-now { font-size: 18px; font-weight: 800; }
  .regime-delta { font-size: 12px; display: flex; flex-direction: column; gap: 2px; }
  .regime-delta small { color: ${TOKENS.muted}; font-size: 9px; }
  .regime-mini-trend svg { display: block; }
  .regime-interpretation { border: 1px solid ${TOKENS.borderSubtle}; background: rgba(13,17,23,.6); border-radius: 8px; padding: 12px; display: grid; gap: 8px; }
  .regime-interp-line { display: flex; align-items: flex-start; gap: 8px; }
  .regime-interp-line i { width: 7px; height: 7px; border-radius: 999px; flex-shrink: 0; margin-top: 3px; }
  .regime-interp-line span { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.5; }
  .regime-interp-line b { color: ${TOKENS.text}; }
`;
```

**Regime Sensitivity Table Component:**

```javascript
function RegimeSensitivityTable({ data }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ regime: "Expansion", expected_return: 0.082, vol: 0.11, sharpe: 0.75, prob: 0.62 }, ...]

  const best = useMemo(() =>
    rows.reduce((b, r) => (numberLike(r.expected_return) ?? -Infinity) > (numberLike(b?.expected_return) ?? -Infinity) ? r : b, null),
  [rows]);
  const worst = useMemo(() =>
    rows.reduce((b, r) => (numberLike(r.expected_return) ?? Infinity) < (numberLike(b?.expected_return) ?? Infinity) ? r : b, null),
  [rows]);

  return (
    <div className="regime-sensitivity">
      <div className="regime-sensitivity-header">
        <div className="regime-sens-best">
          <span>Best Regime for Portfolio</span>
          <strong>{titleize(best?.regime || "—")}</strong>
          <b className="mono positive">+{((numberLike(best?.expected_return) ?? 0) * 100).toFixed(1)}% expected</b>
        </div>
        <div className="regime-sens-worst">
          <span>Worst Regime for Portfolio</span>
          <strong>{titleize(worst?.regime || "—")}</strong>
          <b className="mono negative">{((numberLike(worst?.expected_return) ?? 0) * 100).toFixed(1)}% expected</b>
        </div>
      </div>
      <div className="table-scroll">
        <table className="f2-table">
          <thead>
            <tr>
              <th><button type="button">Regime</button></th>
              <th><button type="button">Prob</button></th>
              <th><button type="button">Exp Return</button></th>
              <th><button type="button">Vol</button></th>
              <th><button type="button">Sharpe</button></th>
              <th><button type="button">Risk-Adj Weight</button></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const ret = numberLike(row.expected_return);
              const vol = numberLike(row.vol ?? row.volatility);
              const sharpe = numberLike(row.sharpe ?? row.sharpe_ratio);
              const prob = numberLike(row.prob ?? row.probability);
              const riskAdj = (prob != null && vol != null && vol > 0) ? (prob / vol) : null;
              const isBest = row === best;
              const isWorst = row === worst;
              return (
                <tr key={i} style={isBest ? { borderLeft: `3px solid ${TOKENS.green}` } : isWorst ? { borderLeft: `3px solid ${TOKENS.red}` } : {}}>
                  <td style={{ textAlign: "left" }}>
                    {isBest ? <span style={{ color: TOKENS.green, marginRight: 6, fontSize: 10, fontWeight: 800 }}>BEST</span> : null}
                    {isWorst ? <span style={{ color: TOKENS.red, marginRight: 6, fontSize: 10, fontWeight: 800 }}>WORST</span> : null}
                    {titleize(row.regime || row.state || `State ${i + 1}`)}
                  </td>
                  <td>{prob != null ? `${(prob * 100).toFixed(1)}%` : "—"}</td>
                  <td className={ret != null ? (ret >= 0 ? "positive" : "negative") : ""}>
                    {ret != null ? `${ret >= 0 ? "+" : ""}${(ret * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td>{vol != null ? `${(vol * 100).toFixed(1)}%` : "—"}</td>
                  <td className={sharpe != null ? (sharpe >= 0.5 ? "positive" : sharpe >= 0 ? "" : "negative") : ""}>
                    {sharpe != null ? sharpe.toFixed(2) : "—"}
                  </td>
                  <td>{riskAdj != null ? riskAdj.toFixed(3) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "regimeSensitivity") return <RegimeSensitivityTable data={data} />;
```

CSS:

```javascript
const regimeSensStyles = `
  .regime-sensitivity { display: grid; gap: 14px; }
  .regime-sensitivity-header { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .regime-sens-best, .regime-sens-worst { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 12px 14px; display: grid; gap: 4px; }
  .regime-sens-best { border-color: rgba(34,197,94,.28); background: rgba(34,197,94,.05); }
  .regime-sens-worst { border-color: rgba(239,68,68,.28); background: rgba(239,68,68,.05); }
  .regime-sens-best span, .regime-sens-worst span { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .12em; font-weight: 800; }
  .regime-sens-best strong, .regime-sens-worst strong { font-size: 16px; color: ${TOKENS.text}; }
`;
```

---

## FEATURE 5: Alpha Decay — Cross-Sector Decay, Factor Signal Power Radar, Multi-Factor Dashboard

### Computation Logic

**Cross-Sector Decay:**

For each GICS sector S and factor F, restrict the universe to stocks in sector S. Compute rank IC at each horizon h:

```
IC_F_S(h) = SpearmanCorr(rank(factor_score_S(T)), rank(ret_S(T, T+h)))
```

Repeat for each sector S. This gives a (K_sectors x K_horizons) matrix of IC values per factor. Fit the hyperbolic model sector-by-sector:

```
IC(h) = a_S / (1 + b_S * h)
```

Extract half-life h*_S = 1/b_S for each sector.

**Factor Signal Power Radar:**

Eight metrics, each normalized to 0-100:

1. IC (20-day): Raw IC vs universe distribution, percentile rank of IC among all factors
2. ICIR: IC / std(IC) over trailing 252 days, normalized
3. Half-life score: 100 - (100 * h* / max_halflife_in_library) so short half-life = high score meaning fast monetization. Inverted as specified because shorter half-life = lower rebalancing cost per unit IC
4. Crowding score (inverted): 100 - current_crowding_percentile
5. Sector concentration HHI (inverted): 100 - (100 * HHI / max_HHI)
6. Regime dependence: Sharpe spread between best and worst macro regime, normalized to 0-100
7. Correlation to nearest neighbor: 100 - (100 * max_pairwise_corr / 1.0) so orthogonal factors score high
8. Factor purity: FF5 alpha as percentage of gross return, already 0-100

---

**Cross-Sector Decay Comparison Component:**

```javascript
function CrossSectorDecay({ data, config = {} }) {
  const [selectedSector, setSelectedSector] = useState(null);
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ sector: "Technology", horizon_1: 0.082, horizon_5: 0.071, horizon_21: 0.048, horizon_63: 0.021, half_life_days: 34 }, ...]

  const sectors = useMemo(() => [...new Set(rows.map((r) => r.sector || r.name))], [rows]);
  const horizons = useMemo(() => {
    const keys = Object.keys(rows[0] || {}).filter((k) => /horizon_\d+|h_\d+/.test(k));
    return keys.sort((a, b) => parseInt(a.replace(/\D/g, "")) - parseInt(b.replace(/\D/g, "")));
  }, [rows]);

  // Build chart data: x = horizon, one line per sector
  const chartRows = useMemo(() => {
    return horizons.map((hKey) => {
      const hDays = parseInt(hKey.replace(/\D/g, ""));
      const row = { horizon: hDays };
      rows.forEach((r) => {
        const sectorName = r.sector || r.name;
        if (!selectedSector || selectedSector === sectorName) {
          row[sectorName] = numberLike(r[hKey]);
        }
      });
      return row;
    });
  }, [rows, horizons, selectedSector]);

  const sectorKeys = selectedSector ? [selectedSector] : sectors;

  return (
    <div className="cross-sector-decay">
      {/* Sector filter pills */}
      <div className="sector-filter-row">
        <button
          className={selectedSector === null ? "active" : ""}
          onClick={() => setSelectedSector(null)}
          type="button"
        >
          All Sectors
        </button>
        {sectors.map((s) => (
          <button
            key={s}
            className={selectedSector === s ? "active" : ""}
            onClick={() => setSelectedSector(selectedSector === s ? null : s)}
            type="button"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Decay curves */}
      <ResponsiveContainer height={400} width="100%">
        <LineChart data={chartRows} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="horizon" label={{ value: "Horizon (trading days)", fill: TOKENS.secondary, fontSize: 11, position: "insideBottom", offset: -4 }} {...axisProps} />
          <YAxis label={{ value: "Rank IC", fill: TOKENS.secondary, fontSize: 11, angle: -90, position: "insideLeft" }} {...axisProps} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeDasharray="3 5" strokeOpacity={0.6} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ color: TOKENS.secondary, fontSize: 11 }} />
          {sectorKeys.map((sector, i) => (
            <Line
              key={sector}
              dataKey={sector}
              stroke={SERIES[i % SERIES.length]}
              strokeWidth={selectedSector === sector ? 3 : 1.5}
              strokeOpacity={selectedSector && selectedSector !== sector ? 0.2 : 1}
              dot={{ r: 4, fill: SERIES[i % SERIES.length], strokeWidth: 0 }}
              type="monotone"
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Half-life comparison table */}
      <div className="sector-halflife-table">
        <div className="sector-halflife-header">Half-Life by Sector</div>
        <div className="sector-halflife-grid">
          {rows
            .filter((r) => !selectedSector || (r.sector || r.name) === selectedSector)
            .sort((a, b) => (numberLike(a.half_life_days) ?? 999) - (numberLike(b.half_life_days) ?? 999))
            .map((row, i) => {
              const hl = numberLike(row.half_life_days ?? row.half_life);
              const maxHl = Math.max(...rows.map((r) => numberLike(r.half_life_days ?? r.half_life) ?? 0));
              const pct = maxHl > 0 && hl != null ? (hl / maxHl) * 100 : 0;
              return (
                <div key={i} className="sector-hl-row">
                  <span>{row.sector || row.name}</span>
                  <div className="sector-hl-bar">
                    <div style={{ width: `${pct}%`, background: SERIES[i % SERIES.length] }} />
                  </div>
                  <b className="mono">{hl != null ? `${hl.toFixed(0)}d` : "—"}</b>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "crossSectorDecay") return <CrossSectorDecay data={data} config={section.config} />;
```

CSS:

```javascript
const crossSectorStyles = `
  .cross-sector-decay { display: grid; gap: 14px; }
  .sector-filter-row { display: flex; flex-wrap: wrap; gap: 6px; }
  .sector-filter-row button { height: 26px; padding: 0 9px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 999px; font-size: 10px; font-weight: 700; cursor: pointer; }
  .sector-filter-row button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.1); }
  .sector-halflife-table { border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 12px; background: ${TOKENS.elevated}; display: grid; gap: 10px; }
  .sector-halflife-header { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .sector-halflife-grid { display: grid; gap: 8px; }
  .sector-hl-row { display: grid; grid-template-columns: 160px 1fr 56px; gap: 10px; align-items: center; }
  .sector-hl-row span { color: ${TOKENS.text}; font-size: 12px; }
  .sector-hl-bar { height: 8px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; }
  .sector-hl-bar div { height: 100%; border-radius: 999px; }
  .sector-hl-row b { text-align: right; font-size: 12px; color: ${TOKENS.text}; }
`;
```

**Factor Signal Power Radar — Multi-Factor Overlay:**

The existing `RadarVisual` handles single-factor. For multi-factor overlay (up to 10 simultaneously), extend it:

```javascript
function MultiFactorRadar({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const [selectedFactors, setSelectedFactors] = useState(() => rows.slice(0, 3).map((r) => r.factor || r.name));

  // Each row: { factor: "momentum_12_1", ic: 78, icir: 65, half_life_score: 42, crowding_score_inv: 55, ... }
  const axes = ["ic", "icir", "half_life_score", "crowding_score_inv", "sector_concentration_inv", "regime_dependence_inv", "correlation_to_nearest_inv", "purity_score"];
  const axisLabels = { ic: "IC", icir: "ICIR", half_life_score: "Half-Life Score", crowding_score_inv: "Uncrowded", sector_concentration_inv: "Diversified", regime_dependence_inv: "Regime-Stable", correlation_to_nearest_inv: "Orthogonal", purity_score: "Purity" };

  // Build recharts RadarChart data: one entry per axis
  const chartData = axes.map((axis) => {
    const entry = { axis: axisLabels[axis] || titleize(axis) };
    selectedFactors.forEach((factor) => {
      const row = rows.find((r) => (r.factor || r.name) === factor);
      entry[factor] = numberLike(row?.[axis]) ?? 0;
    });
    return entry;
  });

  const factorOptions = rows.map((r) => r.factor || r.name);

  return (
    <div className="multi-factor-radar">
      {/* Factor selector */}
      <div className="mfr-selector">
        {factorOptions.map((factor, i) => (
          <button
            key={factor}
            className={selectedFactors.includes(factor) ? "active" : ""}
            style={selectedFactors.includes(factor) ? { borderColor: SERIES[selectedFactors.indexOf(factor) % SERIES.length], color: SERIES[selectedFactors.indexOf(factor) % SERIES.length] } : {}}
            onClick={() => setSelectedFactors((prev) => {
              if (prev.includes(factor)) return prev.filter((f) => f !== factor);
              if (prev.length >= 10) return prev;
              return [...prev, factor];
            })}
            type="button"
          >
            {titleize(factor)}
          </button>
        ))}
      </div>

      {/* Radar chart */}
      <ResponsiveContainer height={480} width="100%">
        <RadarChart data={chartData} outerRadius="72%">
          <PolarGrid stroke={TOKENS.grid} strokeOpacity={0.5} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={{ fill: TOKENS.secondary, fontSize: 9 }} tickCount={5} />
          {selectedFactors.map((factor, i) => (
            <Radar
              key={factor}
              dataKey={factor}
              name={titleize(factor)}
              fill={SERIES[i % SERIES.length]}
              fillOpacity={0.12}
              stroke={SERIES[i % SERIES.length]}
              strokeWidth={2}
            />
          ))}
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ color: TOKENS.secondary, fontSize: 11 }} />
        </RadarChart>
      </ResponsiveContainer>

      {/* Score table */}
      <div className="table-scroll">
        <table className="f2-table">
          <thead>
            <tr>
              <th><button type="button">Factor</button></th>
              {axes.map((axis) => <th key={axis}><button type="button">{axisLabels[axis]}</button></th>)}
              <th><button type="button">Composite</button></th>
            </tr>
          </thead>
          <tbody>
            {rows
              .filter((r) => selectedFactors.includes(r.factor || r.name))
              .map((row, i) => {
                const scores = axes.map((axis) => numberLike(row[axis]) ?? 0);
                const composite = scores.reduce((s, v) => s + v, 0) / scores.length;
                return (
                  <tr key={i}>
                    <td style={{ textAlign: "left" }}>{titleize(row.factor || row.name)}</td>
                    {axes.map((axis) => {
                      const v = numberLike(row[axis]) ?? 0;
                      return <td key={axis} className="mono" style={{ color: v >= 70 ? TOKENS.green : v >= 40 ? TOKENS.text : TOKENS.red }}>{v.toFixed(0)}</td>;
                    })}
                    <td className="mono" style={{ color: composite >= 65 ? TOKENS.green : composite >= 40 ? TOKENS.amber : TOKENS.red }}>{composite.toFixed(0)}</td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "multiFactorRadar") return <MultiFactorRadar data={data} config={section.config} />;
```

CSS:

```javascript
const multiRadarStyles = `
  .multi-factor-radar { display: grid; gap: 14px; }
  .mfr-selector { display: flex; flex-wrap: wrap; gap: 6px; }
  .mfr-selector button { height: 26px; padding: 0 10px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 999px; font-size: 10px; font-weight: 700; cursor: pointer; transition: all 100ms ease; }
  .mfr-selector button.active { background: rgba(245,164,0,.08); }
`;
```

**Multi-Factor Decay Dashboard with Bootstrap Confidence Bands:**

```javascript
function MultiFactorDecayDashboard({ data, config = {} }) {
  const [selected, setSelected] = useState([]);
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ factor: "momentum_12_1", horizon_1: 0.082, horizon_5: 0.071, ..., ci_low_21: 0.028, ci_high_21: 0.068, half_life: 34, model: "hyperbolic" }, ...]

  const factors = useMemo(() => [...new Set(rows.map((r) => r.factor || r.name))], [rows]);
  const activeFactors = selected.length ? selected : factors.slice(0, 4);

  const horizons = useMemo(() => {
    const first = rows.find((r) => (r.factor || r.name) === activeFactors[0]) || {};
    return Object.keys(first).filter((k) => /^horizon_\d+$/.test(k)).sort((a, b) => parseInt(a.slice(8)) - parseInt(b.slice(8)));
  }, [rows, activeFactors]);

  // Build chart data
  const chartRows = useMemo(() => horizons.map((hKey) => {
    const hDays = parseInt(hKey.slice(8));
    const entry = { horizon: hDays };
    activeFactors.forEach((factor) => {
      const row = rows.find((r) => (r.factor || r.name) === factor);
      if (!row) return;
      entry[`${factor}_ic`] = numberLike(row[hKey]);
      entry[`${factor}_ci_low`] = numberLike(row[`ci_low_${hDays}`] ?? row[`ci_lower_${hKey.slice(8)}`]);
      entry[`${factor}_ci_high`] = numberLike(row[`ci_high_${hDays}`] ?? row[`ci_upper_${hKey.slice(8)}`]);
    });
    return entry;
  }), [rows, activeFactors, horizons]);

  return (
    <div className="multi-decay-dashboard">
      <div className="decay-factor-selector">
        {factors.map((f, i) => (
          <button
            key={f}
            className={activeFactors.includes(f) ? "active" : ""}
            style={activeFactors.includes(f) ? { borderColor: SERIES[activeFactors.indexOf(f) % SERIES.length] } : {}}
            onClick={() => setSelected((prev) => {
              if (prev.includes(f)) return prev.filter((x) => x !== f);
              if (prev.length >= 10) return prev;
              return [...prev, f];
            })}
            type="button"
          >
            {titleize(f)}
          </button>
        ))}
      </div>

      <ResponsiveContainer height={440} width="100%">
        <ComposedDecayChart chartRows={chartRows} activeFactors={activeFactors} />
      </ResponsiveContainer>

      {/* Half-life summary strip */}
      <div className="decay-halflife-strip">
        {activeFactors.map((factor, i) => {
          const row = rows.find((r) => (r.factor || r.name) === factor);
          const hl = numberLike(row?.half_life ?? row?.half_life_days);
          const model = row?.model || "hyperbolic";
          return (
            <div key={factor} className="decay-hl-card" style={{ borderColor: `${SERIES[i % SERIES.length]}40` }}>
              <i style={{ background: SERIES[i % SERIES.length] }} />
              <span>{titleize(factor)}</span>
              <b className="mono">{hl != null ? `${hl.toFixed(0)}d` : "—"}</b>
              <small>{model}</small>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Recharts does not natively support filled confidence bands per series in LineChart without Area trick.
// Use AreaChart with multiple transparent-fill areas for CI bands plus Line on top:
function ComposedDecayChart({ chartRows, activeFactors }) {
  return (
    <ResponsiveContainer height={440} width="100%">
      <AreaChart data={chartRows} margin={{ top: 14, right: 28, left: 6, bottom: 22 }}>
        <defs>
          {activeFactors.map((factor, i) => (
            <linearGradient key={factor} id={`decay-ci-${i}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.14} />
              <stop offset="100%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.04} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
        <XAxis dataKey="horizon" label={{ value: "Horizon (trading days)", fill: TOKENS.secondary, fontSize: 10, position: "insideBottom", offset: -8 }} {...axisProps} />
        <YAxis label={{ value: "Rank IC", fill: TOKENS.secondary, fontSize: 10, angle: -90, position: "insideLeft" }} {...axisProps} />
        <ReferenceLine y={0} stroke={TOKENS.secondary} strokeDasharray="3 5" strokeOpacity={0.55} />
        <Tooltip content={<CustomTooltip />} />
        {/* CI bands per factor */}
        {activeFactors.map((factor, i) => (
          <Area
            key={`${factor}-ci`}
            dataKey={`${factor}_ci_high`}
            fill={`url(#decay-ci-${i})`}
            stroke="none"
            type="monotone"
            legendType="none"
          />
        ))}
        {/* IC lines per factor */}
        {activeFactors.map((factor, i) => (
          <Area
            key={`${factor}-ic`}
            dataKey={`${factor}_ic`}
            stroke={SERIES[i % SERIES.length]}
            strokeWidth={2.5}
            fill="none"
            dot={{ r: 4, fill: SERIES[i % SERIES.length], strokeWidth: 0 }}
            type="monotone"
            name={titleize(factor)}
          />
        ))}
        <Legend wrapperStyle={{ color: TOKENS.secondary, fontSize: 11 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "multiFactorDecay") return <MultiFactorDecayDashboard data={data} config={section.config} />;
```

CSS:

```javascript
const multiDecayStyles = `
  .multi-decay-dashboard { display: grid; gap: 14px; }
  .decay-factor-selector { display: flex; flex-wrap: wrap; gap: 6px; }
  .decay-factor-selector button { height: 26px; padding: 0 9px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 999px; font-size: 10px; font-weight: 700; cursor: pointer; }
  .decay-factor-selector button.active { background: rgba(245,164,0,.06); color: ${TOKENS.text}; }
  .decay-halflife-strip { display: flex; flex-wrap: wrap; gap: 8px; }
  .decay-hl-card { display: flex; align-items: center; gap: 8px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 8px 10px; }
  .decay-hl-card i { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
  .decay-hl-card span { color: ${TOKENS.secondary}; font-size: 11px; }
  .decay-hl-card b { font-size: 14px; }
  .decay-hl-card small { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .1em; }
`;
```

---

## FEATURE 6: Crowding Monitor — Heatmap Behind Return Chart and Crash Annotations

### Computation Logic

**Crowding Percentile Heatmap Behind Factor Return:**

The key insight is that the crowding percentile series and the factor return series share the same time axis. The crowding percentile is rendered as a background `ReferenceArea` color band, updated at daily frequency. Since Recharts does not natively support a continuous background heatmap gradient driven by a secondary data series, the technique is to divide the x-axis into segments and add a `ReferenceArea` for each date range where the crowding percentile falls in a given color bucket.

**Implementation approach:**

Pre-process the crowding series server-side into contiguous date-range segments by color bucket (green/amber/red). Return as `crowding_bands` array: `[{ date_start, date_end, level: "green"|"amber"|"red" }]`.

```javascript
function CrowdingReturnOverlay({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data?.factor_returns ?? data?.returns ?? data), [data]);
  const bands = useMemo(() => Array.isArray(data?.crowding_bands) ? data.crowding_bands : [], [data]);
  const crashAnnotations = useMemo(() => Array.isArray(data?.crash_annotations) ? data.crash_annotations : [], [data]);
  const { xKey, yKeys } = useMemo(() => inferKeys(rows, config), [rows, config]);

  const bandColor = (level) => ({
    green: "rgba(34,197,94,0.08)",
    amber: "rgba(245,164,0,0.09)",
    red: "rgba(239,68,68,0.11)",
  }[level] || "transparent");

  return (
    <div className="crowding-return-overlay">
      <div className="cro-legend">
        <div className="cro-legend-item"><i style={{ background: "rgba(34,197,94,0.25)" }} /><span>Uncrowded (below 40th pct)</span></div>
        <div className="cro-legend-item"><i style={{ background: "rgba(245,164,0,0.25)" }} /><span>Elevated (40-70th pct)</span></div>
        <div className="cro-legend-item"><i style={{ background: "rgba(239,68,68,0.25)" }} /><span>Extreme (above 70th pct)</span></div>
      </div>
      <ResponsiveContainer height={440} width="100%">
        <AreaChart data={rows} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <defs>
            {yKeys.map((key, i) => (
              <linearGradient key={key} id={`cro-grad-${key}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.3} />
                <stop offset="100%" stopColor={SERIES[i % SERIES.length]} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.4} vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          {/* Crowding regime background bands */}
          {bands.map((band, i) => (
            <ReferenceArea
              key={i}
              x1={band.date_start}
              x2={band.date_end}
              fill={bandColor(band.level)}
              fillOpacity={1}
            />
          ))}
          {/* Crash event vertical lines with annotations */}
          {crashAnnotations.map((crash, i) => (
            <ReferenceLine
              key={i}
              x={crash.date}
              stroke={TOKENS.red}
              strokeWidth={1.5}
              strokeDasharray="3 4"
              label={{
                value: crash.label,
                fill: TOKENS.red,
                fontSize: 9,
                angle: -90,
                position: "insideTopLeft",
                offset: 5,
              }}
            />
          ))}
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeOpacity={0.4} />
          {yKeys.map((key, i) => (
            <Area
              key={key}
              dataKey={key}
              stroke={SERIES[i % SERIES.length]}
              strokeWidth={2}
              fill={`url(#cro-grad-${key})`}
              type="monotone"
              dot={false}
            />
          ))}
          {rows.length > 20 && <Brush dataKey={xKey} fill={TOKENS.elevated} height={28} stroke={TOKENS.border} />}
        </AreaChart>
      </ResponsiveContainer>
      {/* Crash annotation table */}
      {crashAnnotations.length ? (
        <div className="crash-annotation-table">
          <div className="cat-header">Historical Crash Episodes with Crowding Context</div>
          {crashAnnotations.map((crash, i) => {
            const crowdingAtCrash = numberLike(crash.crowding_pct_at_crash);
            return (
              <div key={i} className="cat-row">
                <b className="mono" style={{ color: TOKENS.red }}>{crash.date}</b>
                <span>{crash.label}</span>
                {crowdingAtCrash != null ? (
                  <div className="cat-crowding">
                    <div className="cat-crowding-bar">
                      <div style={{ width: `${crowdingAtCrash}%`, background: crowdingAtCrash >= 70 ? TOKENS.red : TOKENS.amber }} />
                    </div>
                    <b className="mono">{crowdingAtCrash.toFixed(0)}th pct</b>
                  </div>
                ) : null}
                {crash.factor_return != null ? (
                  <b className={`mono ${crash.factor_return < 0 ? "negative" : "positive"}`}>
                    {crash.factor_return >= 0 ? "+" : ""}{(crash.factor_return * 100).toFixed(1)}% factor ret
                  </b>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "crowdingReturnOverlay") return <CrowdingReturnOverlay data={data} config={section.config} />;
```

CSS:

```javascript
const crowdingOverlayStyles = `
  .crowding-return-overlay { display: grid; gap: 14px; }
  .cro-legend { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
  .cro-legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: ${TOKENS.secondary}; }
  .cro-legend-item i { width: 14px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .crash-annotation-table { border: 1px solid rgba(239,68,68,.25); background: rgba(239,68,68,.04); border-radius: 8px; padding: 12px; display: grid; gap: 8px; }
  .cat-header { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .cat-row { display: grid; grid-template-columns: 90px 1fr 140px 120px; gap: 10px; align-items: center; border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 7px; }
  .cat-row:first-of-type { border-top: 0; }
  .cat-row span { color: ${TOKENS.secondary}; font-size: 11px; }
  .cat-crowding { display: flex; align-items: center; gap: 8px; }
  .cat-crowding-bar { flex: 1; height: 6px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; }
  .cat-crowding-bar div { height: 100%; border-radius: 999px; }
  .cat-crowding b { font-size: 11px; white-space: nowrap; }
`;
```

---

## FEATURE 7: Backtesting — Full Decile Analysis D1-D10, OOS Toggle, ADV Capacity Curve

### Full Decile Analysis Component

```javascript
function DecileReturnChart({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ decile: "D1", return_ann: 0.186, sharpe: 1.42, volatility: 0.13, max_dd: -0.18 }, ...]

  const [metric, setMetric] = useState("return_ann");
  const metricOptions = [
    { key: "return_ann", label: "Ann. Return" },
    { key: "sharpe", label: "Sharpe" },
    { key: "volatility", label: "Volatility" },
    { key: "max_dd", label: "Max Drawdown" },
    { key: "hit_rate", label: "Hit Rate" },
  ];

  const chartData = useMemo(() => rows.map((r) => ({
    decile: r.decile || r.name,
    value: numberLike(r[metric]) ?? 0,
  })), [rows, metric]);

  // Monotonicity check: D1 should have highest return, D10 lowest (or vice versa)
  const violations = useMemo(() => {
    const returns = rows.map((r) => numberLike(r.return_ann) ?? 0);
    let v = 0;
    for (let i = 1; i < returns.length; i++) {
      if (returns[i] > returns[i - 1]) v++;
    }
    return v;
  }, [rows]);

  return (
    <div className="decile-chart">
      {/* Metric selector */}
      <div className="decile-metric-selector">
        {metricOptions.map((opt) => (
          <button
            key={opt.key}
            className={metric === opt.key ? "active" : ""}
            onClick={() => setMetric(opt.key)}
            type="button"
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Monotonicity warning */}
      {violations > 2 && metric === "return_ann" ? (
        <div className="monotone-warning">
          <AlertTriangle size={14} />
          <span>{violations} monotonicity violations detected. This factor does not rank stocks reliably across all deciles.</span>
        </div>
      ) : violations === 0 && metric === "return_ann" && rows.length >= 5 ? (
        <div className="monotone-pass">
          <CheckCircle2 size={14} />
          <span>Perfect monotonicity — factor return declines cleanly from D1 to D{rows.length}. Signal is robust across the full return distribution.</span>
        </div>
      ) : null}

      {/* Bar chart */}
      <ResponsiveContainer height={380} width="100%">
        <BarChart data={chartData} margin={{ top: 14, right: 26, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="decile" {...axisProps} />
          <YAxis {...axisProps} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeOpacity={0.5} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => {
              // Check monotonicity violation for this cell
              const prev = chartData[i - 1];
              const violates = prev && entry.value > prev.value && metric === "return_ann";
              return (
                <Cell
                  key={i}
                  fill={violates ? TOKENS.amber : entry.value >= 0 ? TOKENS.green : TOKENS.red}
                  stroke={violates ? TOKENS.amber : undefined}
                  strokeDasharray={violates ? "4 3" : undefined}
                  strokeWidth={violates ? 2 : 0}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Full stats table */}
      <DataTable data={rows} config={{ colorBySign: true }} />
    </div>
  );
}
```

**OOS Split Toggle:**

```javascript
function OOSSplitToggle({ response, section }) {
  const [mode, setMode] = useState("combined");
  // response contains: charts.equity_curve_is (in-sample), charts.equity_curve_oos (out-of-sample), charts.equity_curve_combined
  const dataKeyMap = {
    combined: "equity_curve_combined",
    is: "equity_curve_is",
    oos: "equity_curve_oos",
  };
  const currentData = response?.charts?.[dataKeyMap[mode]];
  const oosStats = response?.tables?.oos_stats;
  const isStats = response?.tables?.is_stats;

  return (
    <div className="oos-split">
      <div className="oos-controls">
        {[["combined", "Full History"], ["is", "In-Sample Only"], ["oos", "Out-of-Sample Only"]].map(([key, label]) => (
          <button
            key={key}
            className={mode === key ? "active" : ""}
            onClick={() => setMode(key)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      {/* OOS Sharpe prominently displayed */}
      {mode === "oos" && oosStats ? (
        <div className="oos-headline">
          <div className="oos-sharpe-card">
            <span>Out-of-Sample Sharpe (Primary)</span>
            <strong className={`mono ${(numberLike(rowsFrom(oosStats).find((r) => /sharpe/i.test(r.metric || r.name || ""))?.value) ?? 0) >= 0.5 ? "positive" : "negative"}`}>
              <AnimatedNumber value={rowsFrom(oosStats).find((r) => /sharpe/i.test(r.metric || r.name || ""))?.value} />
            </strong>
            <small>The definitive measure of signal validity. In-sample Sharpe is a training artifact.</small>
          </div>
          {isStats ? (
            <div className="oos-is-comparison">
              <span>In-Sample Sharpe</span>
              <b className="mono secondary">{formatValue(rowsFrom(isStats).find((r) => /sharpe/i.test(r.metric || r.name || ""))?.value)}</b>
              <small>OOS decay = {
                (() => {
                  const oosS = numberLike(rowsFrom(oosStats).find((r) => /sharpe/i.test(r.metric || r.name || ""))?.value);
                  const isS = numberLike(rowsFrom(isStats).find((r) => /sharpe/i.test(r.metric || r.name || ""))?.value);
                  if (oosS == null || isS == null || isS === 0) return "—";
                  const decay = ((oosS - isS) / Math.abs(isS)) * 100;
                  return `${decay >= 0 ? "+" : ""}${decay.toFixed(1)}%`;
                })()
              }</small>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Equity curve with OOS region highlighted */}
      <BacktestSplit response={{ ...response, charts: { ...response?.charts, equity_curve_combined: currentData } }} section={{ ...section, dataKey: "equity_curve_combined" }} />

      {/* Stats table */}
      <DataTable data={mode === "oos" ? oosStats : mode === "is" ? isStats : response?.tables?.combined_stats} config={{ colorBySign: true }} />
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "oosSplit") return <OOSSplitToggle response={response} section={section} />;
if (section.chartType === "decileReturn") return <DecileReturnChart data={data} config={section.config} />;
```

CSS:

```javascript
const oosSplitStyles = `
  .oos-split { display: grid; gap: 14px; }
  .oos-controls { display: flex; gap: 6px; }
  .oos-controls button { height: 30px; padding: 0 12px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 5px; font-size: 11px; font-weight: 700; cursor: pointer; }
  .oos-controls button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.08); }
  .oos-headline { display: grid; grid-template-columns: 1fr auto; gap: 12px; }
  .oos-sharpe-card { border: 1px solid rgba(34,197,94,.3); background: rgba(34,197,94,.06); border-radius: 8px; padding: 14px 16px; display: grid; gap: 4px; }
  .oos-sharpe-card span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; font-weight: 800; }
  .oos-sharpe-card strong { font-size: 36px; font-weight: 800; }
  .oos-sharpe-card small { color: ${TOKENS.secondary}; font-size: 11px; line-height: 1.4; }
  .oos-is-comparison { border: 1px solid ${TOKENS.border}; border-radius: 8px; padding: 14px; display: grid; gap: 4px; align-content: center; }
  .oos-is-comparison span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .oos-is-comparison b { font-size: 22px; color: ${TOKENS.secondary}; }
  .oos-is-comparison small { color: ${TOKENS.muted}; font-size: 11px; }
  .monotone-warning { display: flex; align-items: center; gap: 8px; border: 1px solid rgba(245,164,0,.35); background: rgba(245,164,0,.07); border-radius: 7px; padding: 10px 12px; color: ${TOKENS.amber}; font-size: 12px; }
  .monotone-pass { display: flex; align-items: center; gap: 8px; border: 1px solid rgba(34,197,94,.3); background: rgba(34,197,94,.06); border-radius: 7px; padding: 10px 12px; color: ${TOKENS.green}; font-size: 12px; }
  .decile-chart { display: grid; gap: 14px; }
  .decile-metric-selector { display: flex; gap: 6px; flex-wrap: wrap; }
  .decile-metric-selector button { height: 26px; padding: 0 9px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 999px; font-size: 10px; font-weight: 700; cursor: pointer; }
  .decile-metric-selector button.active { color: ${TOKENS.amber}; border-color: rgba(245,164,0,.45); background: rgba(245,164,0,.1); }
`;
```

**ADV Capacity Curve inside F07:**

```javascript
function AdvCapacityCurve({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ aum_usd: 1e6, net_alpha_bps: 182, slippage_bps: 14, capacity_ceiling: false }, ...]

  const ceilingPoint = useMemo(() => rows.find((r) => r.capacity_ceiling || (numberLike(r.net_alpha_bps) ?? 1) <= 0), [rows]);
  const optimalPoint = useMemo(() => {
    if (!rows.length) return null;
    return [...rows].sort((a, b) => (numberLike(b.net_alpha_bps) ?? 0) - (numberLike(a.net_alpha_bps) ?? 0))[0];
  }, [rows]);

  return (
    <div className="adv-capacity-curve">
      {/* Summary cards */}
      <div className="capacity-summary">
        <div className="capacity-card">
          <span>Capacity Ceiling</span>
          <strong className="mono negative">{ceilingPoint ? `$${(numberLike(ceilingPoint.aum_usd) / 1e6).toFixed(0)}M` : ">$10B"}</strong>
          <small>AUM at which net alpha crosses zero</small>
        </div>
        <div className="capacity-card">
          <span>Optimal AUM (~50% of ceiling)</span>
          <strong className="mono positive">{optimalPoint ? `$${(numberLike(optimalPoint.aum_usd) / 1e6).toFixed(0)}M` : "—"}</strong>
          <small>Net alpha peaks here; {formatValue(optimalPoint?.net_alpha_bps)} bps after costs</small>
        </div>
      </div>

      <ResponsiveContainer height={400} width="100%">
        <ComposedChart data={rows} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="aum_usd" scale="log" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => v >= 1e9 ? `$${(v/1e9).toFixed(1)}B` : `$${(v/1e6).toFixed(0)}M`} {...axisProps} />
          <YAxis yAxisId="alpha" {...axisProps} label={{ value: "Net Alpha (bps)", fill: TOKENS.secondary, fontSize: 10, angle: -90, position: "insideLeft" }} />
          <YAxis yAxisId="slippage" orientation="right" {...axisProps} label={{ value: "Slippage (bps)", fill: TOKENS.secondary, fontSize: 10, angle: 90, position: "insideRight" }} />
          <Tooltip content={<CustomTooltip />} formatter={(value, name) => name.includes("aum") ? `$${(value/1e6).toFixed(0)}M` : `${value} bps`} />
          {/* Zero line */}
          <ReferenceLine yAxisId="alpha" y={0} stroke={TOKENS.red} strokeDasharray="4 4" strokeOpacity={0.7} label={{ value: "Capacity Ceiling", fill: TOKENS.red, fontSize: 9, position: "insideTopRight" }} />
          {/* Optimal AUM marker */}
          {optimalPoint ? (
            <ReferenceLine yAxisId="alpha" x={numberLike(optimalPoint.aum_usd)} stroke={TOKENS.green} strokeDasharray="4 4" label={{ value: "Optimal AUM", fill: TOKENS.green, fontSize: 9, position: "insideTopRight" }} />
          ) : null}
          {/* Net alpha curve */}
          <Line yAxisId="alpha" dataKey="net_alpha_bps" stroke={TOKENS.accent} strokeWidth={2.5} dot={false} type="monotone" name="Net Alpha (bps)" />
          {/* Slippage curve */}
          <Line yAxisId="slippage" dataKey="slippage_bps" stroke={TOKENS.red} strokeWidth={1.5} strokeDasharray="5 5" dot={false} type="monotone" name="Slippage (bps)" />
        </ComposedChart>
      </ResponsiveContainer>

      <DataTable data={rows} config={{ colorBySign: true, viableColumn: "net_alpha_bps" }} />
    </div>
  );
}
```

You need to import `ComposedChart, Line` already in your recharts imports block. Add to RenderFeatureSection:

```javascript
if (section.chartType === "advCapacityCurve") return <AdvCapacityCurve data={data} config={section.config} />;
```

CSS:

```javascript
const advCapacityStyles = `
  .adv-capacity-curve { display: grid; gap: 14px; }
  .capacity-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .capacity-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 14px 16px; display: grid; gap: 4px; }
  .capacity-card span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; font-weight: 800; }
  .capacity-card strong { font-size: 28px; }
  .capacity-card small { color: ${TOKENS.secondary}; font-size: 11px; line-height: 1.4; }
`;
```

---

## FEATURE 8: Factor Covariance — Hierarchical Clustered Heatmap and Crisis Preset Selector

### Hierarchical Clustered Heatmap

The existing `Heatmap` component already has a `cluster` sort mode via `clusterSortLabels`. To make it fully hierarchical, extend `clusterSortLabels` with a proper greedy single-linkage clustering that also draws dendrogram-like visual groupings:

```javascript
function HierarchicalHeatmap({ data, config = {} }) {
  const [clusterMode, setClusterMode] = useState("cluster");
  const [showDendrogram, setShowDendrogram] = useState(true);

  // Build cluster groups from sorted labels
  const cells = useMemo(() => {
    if (Array.isArray(data?.matrix) && Array.isArray(data?.columns)) {
      return data.matrix.flatMap((row, ri) => row.map((value, ci) => ({
        row: data.index?.[ri] || ri,
        col: data.columns[ci],
        value,
      })));
    }
    return rowsFrom(data).flatMap((row, ri) => {
      const rowName = row.row || row.name || row.factor || ri;
      return Object.entries(row).filter(([k]) => !["row", "name", "factor"].includes(k)).map(([k, v]) => ({ row: rowName, col: k, value: v }));
    });
  }, [data]);

  const allLabels = useMemo(() => [...new Set(cells.map((c) => String(c.row)))], [cells]);
  const clusteredLabels = useMemo(() => clusterMode === "cluster" ? clusterSortLabels(cells, allLabels) : allLabels, [cells, allLabels, clusterMode]);

  // Identify cluster groups: consecutive labels with high pairwise correlation
  const clusterGroups = useMemo(() => {
    if (clusterMode !== "cluster" || clusteredLabels.length < 2) return [];
    const matrix = new Map();
    cells.forEach((c) => {
      if (!matrix.has(c.row)) matrix.set(c.row, new Map());
      matrix.get(c.row).set(c.col, numberLike(c.value) ?? 0);
    });
    const groups = [];
    let groupStart = 0;
    const THRESHOLD = 0.45;
    for (let i = 1; i < clusteredLabels.length; i++) {
      const corr = Math.abs(matrix.get(clusteredLabels[i - 1])?.get(clusteredLabels[i]) ?? matrix.get(clusteredLabels[i])?.get(clusteredLabels[i - 1]) ?? 0);
      if (corr < THRESHOLD || i === clusteredLabels.length - 1) {
        if (i - groupStart > 1) {
          groups.push({ start: groupStart, end: i - (corr < THRESHOLD ? 1 : 0), labels: clusteredLabels.slice(groupStart, i - (corr < THRESHOLD ? 1 : 0) + 1) });
        }
        groupStart = i;
      }
    }
    return groups;
  }, [cells, clusteredLabels, clusterMode]);

  return (
    <div className="hierarchical-heatmap">
      <div className="hh-controls">
        <select value={clusterMode} onChange={(e) => setClusterMode(e.target.value)}>
          <option value="native">Native order</option>
          <option value="cluster">Hierarchical cluster</option>
          <option value="magnitude">Loading magnitude</option>
          <option value="name">Alphabetical</option>
        </select>
        {clusterMode === "cluster" && (
          <label className="hh-toggle">
            <input type="checkbox" checked={showDendrogram} onChange={(e) => setShowDendrogram(e.target.checked)} />
            Show cluster boundaries
          </label>
        )}
        <span className="hh-cluster-count">
          {clusterGroups.length > 0 ? `${clusterGroups.length} cluster groups detected` : ""}
        </span>
      </div>

      {/* Cluster group labels */}
      {showDendrogram && clusterGroups.length > 0 ? (
        <div className="cluster-group-strip">
          {clusterGroups.map((g, i) => (
            <div key={i} className="cluster-group-badge" style={{ borderColor: SERIES[i % SERIES.length], color: SERIES[i % SERIES.length] }}>
              Cluster {i + 1}: {g.labels.map((l) => titleize(l)).join(", ")}
            </div>
          ))}
        </div>
      ) : null}

      <Heatmap data={data} config={{ ...config, sortMode: clusterMode }} />
    </div>
  );
}
```

**Crisis Period Preset Selector with Comparison:**

```javascript
function CrisisPresetComparison({ response, section }) {
  const presets = [
    { key: "gfc_2008", label: "GFC 2008", date_range: "2008-09-01:2009-03-31" },
    { key: "covid_2020", label: "COVID Mar 2020", date_range: "2020-02-15:2020-04-15" },
    { key: "rate_shock_2022", label: "Rate Shock 2022", date_range: "2022-09-01:2022-12-31" },
    { key: "liberation_day_2025", label: "Liberation Day Apr 2025", date_range: "2025-03-15:2025-05-31" },
    { key: "quant_unwind_2025", label: "Quant Unwind Jul 2025", date_range: "2025-07-01:2025-10-31" },
  ];
  const [selectedPresets, setSelectedPresets] = useState(["gfc_2008", "covid_2020"]);

  const togglePreset = (key) => {
    setSelectedPresets((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : prev.length < 4 ? [...prev, key] : prev
    );
  };

  return (
    <div className="crisis-preset-comparison">
      <div className="crisis-preset-selector">
        {presets.map((p, i) => (
          <button
            key={p.key}
            className={selectedPresets.includes(p.key) ? "active" : ""}
            style={selectedPresets.includes(p.key) ? { borderColor: SERIES[selectedPresets.indexOf(p.key) % SERIES.length] } : {}}
            onClick={() => togglePreset(p.key)}
            type="button"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Side-by-side covariance comparison for selected presets */}
      <div className="crisis-comparison-grid" style={{ gridTemplateColumns: `repeat(${Math.min(selectedPresets.length, 2)}, 1fr)` }}>
        {selectedPresets.map((presetKey, i) => {
          const preset = presets.find((p) => p.key === presetKey);
          const presetData = response?.charts?.[`covariance_${presetKey}`] ?? response?.charts?.normal_covariance;
          return (
            <div key={presetKey} className="crisis-comparison-panel" style={{ borderColor: `${SERIES[i % SERIES.length]}40` }}>
              <div className="crisis-comparison-header" style={{ color: SERIES[i % SERIES.length] }}>
                {preset?.label}
              </div>
              <Heatmap data={presetData} config={{ palette: "diverging" }} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "hierarchicalHeatmap") return <HierarchicalHeatmap data={data} config={section.config} />;
if (section.chartType === "crisisPresetComparison") return <CrisisPresetComparison response={response} section={section} />;
```

CSS:

```javascript
const crisisPresetStyles = `
  .hierarchical-heatmap { display: grid; gap: 10px; }
  .hh-controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .hh-controls select { height: 28px; border: 1px solid ${TOKENS.border}; background: ${TOKENS.input}; color: ${TOKENS.text}; border-radius: 5px; padding: 0 8px; font-size: 11px; }
  .hh-toggle { display: flex; align-items: center; gap: 6px; color: ${TOKENS.secondary}; font-size: 11px; cursor: pointer; }
  .hh-toggle input { accent-color: ${TOKENS.accent}; }
  .hh-cluster-count { color: ${TOKENS.muted}; font-size: 10px; font-family: "Quant360 Mono","JetBrains Mono",monospace; margin-left: auto; }
  .cluster-group-strip { display: flex; flex-wrap: wrap; gap: 6px; }
  .cluster-group-badge { border: 1px solid; border-radius: 5px; padding: 5px 9px; font-size: 10px; background: transparent; }
  .crisis-preset-comparison { display: grid; gap: 14px; }
  .crisis-preset-selector { display: flex; flex-wrap: wrap; gap: 6px; }
  .crisis-preset-selector button { height: 28px; padding: 0 10px; border: 1px solid ${TOKENS.border}; background: transparent; color: ${TOKENS.muted}; border-radius: 5px; font-size: 10px; font-weight: 700; cursor: pointer; }
  .crisis-preset-selector button.active { background: rgba(245,164,0,.06); color: ${TOKENS.text}; }
  .crisis-comparison-grid { display: grid; gap: 14px; }
  .crisis-comparison-panel { border: 1px solid ${TOKENS.border}; border-radius: 8px; padding: 12px; display: grid; gap: 8px; }
  .crisis-comparison-header { font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
`;
```

---

## FEATURE 9: Capacity Analyzer — 50-Point Dense Sweep and Full Sensitivity Cube

### Full Capacity Sensitivity Cube

The sensitivity cube varies three dimensions: AUM, rebalancing frequency, and ADV cap. Return a 3D result set flattened as rows: `[{ aum, rebalance_freq, adv_cap, net_alpha_bps, capacity_ceiling_usd }]`.

```javascript
function CapacitySensitivityCube({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);

  // Get unique values for each dimension
  const frequencies = useMemo(() => [...new Set(rows.map((r) => r.rebalance_freq || r.frequency))], [rows]);
  const advCaps = useMemo(() => [...new Set(rows.map((r) => r.adv_cap || r.adv_participation_cap))], [rows]);

  const [selectedFreq, setSelectedFreq] = useState(frequencies[0]);
  const [selectedAdv, setSelectedAdv] = useState(advCaps[advCaps.length - 1]);

  const filteredRows = useMemo(() =>
    rows.filter((r) =>
      (r.rebalance_freq || r.frequency) === selectedFreq &&
      (r.adv_cap || r.adv_participation_cap) === selectedAdv
    ),
  [rows, selectedFreq, selectedAdv]);

  return (
    <div className="capacity-sensitivity-cube">
      {/* Dimension selectors */}
      <div className="cube-controls">
        <div className="cube-dim">
          <span>Rebalancing Frequency</span>
          <div className="pro-chips">
            {frequencies.map((f) => (
              <button
                key={String(f)}
                className={selectedFreq === f ? "active" : ""}
                onClick={() => setSelectedFreq(f)}
                type="button"
              >
                {titleize(String(f))}
              </button>
            ))}
          </div>
        </div>
        <div className="cube-dim">
          <span>ADV Participation Cap</span>
          <div className="pro-chips">
            {advCaps.map((cap) => (
              <button
                key={String(cap)}
                className={selectedAdv === cap ? "active" : ""}
                onClick={() => setSelectedAdv(cap)}
                type="button"
              >
                {typeof cap === "number" ? `${(cap * 100).toFixed(0)}%` : String(cap)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Capacity curve for selected slice */}
      <AdvCapacityCurve data={filteredRows} />

      {/* Full sensitivity matrix: capacity ceiling by freq × ADV cap */}
      <div className="cube-matrix-wrap">
        <div className="cube-matrix-label">Capacity Ceiling ($M) by Frequency × ADV Cap</div>
        <div className="cube-matrix" style={{ gridTemplateColumns: `160px repeat(${advCaps.length}, 1fr)` }}>
          <div className="cube-cell cube-head" />
          {advCaps.map((cap) => (
            <div key={String(cap)} className="cube-cell cube-head">
              {typeof cap === "number" ? `${(cap * 100).toFixed(0)}% ADV` : String(cap)}
            </div>
          ))}
          {frequencies.map((freq) => [
            <div key={`${freq}-label`} className="cube-cell cube-row-label">{titleize(String(freq))}</div>,
            ...advCaps.map((cap) => {
              const match = rows.find((r) =>
                (r.rebalance_freq || r.frequency) === freq &&
                (r.adv_cap || r.adv_participation_cap) === cap
              );
              const ceiling = numberLike(match?.capacity_ceiling_usd ?? match?.capacity_ceiling);
              const isActive = freq === selectedFreq && cap === selectedAdv;
              return (
                <div
                  key={`${freq}-${cap}`}
                  className={`cube-cell cube-data mono ${isActive ? "active" : ""}`}
                  onClick={() => { setSelectedFreq(freq); setSelectedAdv(cap); }}
                >
                  {ceiling != null ? `$${ceiling >= 1e9 ? `${(ceiling/1e9).toFixed(1)}B` : `${(ceiling/1e6).toFixed(0)}M`}` : "—"}
                </div>
              );
            }),
          ])}
        </div>
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "capacitySensitivityCube") return <CapacitySensitivityCube data={data} config={section.config} />;
```

CSS:

```javascript
const capacityCubeStyles = `
  .capacity-sensitivity-cube { display: grid; gap: 18px; }
  .cube-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .cube-dim { display: grid; gap: 6px; }
  .cube-dim span { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .14em; font-weight: 800; }
  .cube-matrix-wrap { overflow: auto; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; }
  .cube-matrix-label { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; padding: 8px 12px; background: ${TOKENS.elevated}; border-bottom: 1px solid ${TOKENS.borderSubtle}; }
  .cube-matrix { display: grid; }
  .cube-cell { min-height: 38px; display: flex; align-items: center; justify-content: flex-end; border-bottom: 1px solid ${TOKENS.grid}; border-right: 1px solid ${TOKENS.grid}; padding: 0 10px; font-size: 11px; }
  .cube-head { background: ${TOKENS.elevated}; color: ${TOKENS.text}; font-weight: 700; justify-content: flex-end; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; }
  .cube-row-label { justify-content: flex-start; background: ${TOKENS.elevated}; font-weight: 700; font-size: 11px; position: sticky; left: 0; z-index: 1; }
  .cube-data { color: ${TOKENS.text}; cursor: pointer; transition: background 80ms ease; }
  .cube-data:hover { background: ${TOKENS.active}; }
  .cube-data.active { background: rgba(245,164,0,.12); border: 1px solid rgba(245,164,0,.4); color: ${TOKENS.amber}; }
`;
```

---

## FEATURE 10: Portfolio Optimizer — Rebalancing Cost-vs-Benefit Chart and Factor Exposure Push to F02

### Rebalancing Cost vs Benefit Chart

```javascript
function RebalancingCostBenefit({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ date: "2024-01-31", sharpe_improvement: 0.08, transaction_cost_bps: 12.4, net_value_bps: 7.2, should_rebalance: true }, ...]

  const [threshold, setThreshold] = useState(0);

  const chartData = useMemo(() => rows.map((r) => ({
    date: r.date || r.period,
    sharpe_benefit: numberLike(r.sharpe_improvement ?? r.benefit) ?? 0,
    cost_bps: numberLike(r.transaction_cost_bps ?? r.cost_bps) ?? 0,
    net_value: numberLike(r.net_value_bps ?? r.net_value) ?? 0,
    rebalance: r.should_rebalance ? 1 : 0,
  })), [rows]);

  return (
    <div className="rebalancing-cost-benefit">
      <div className="rcb-summary">
        <div className="rcb-card">
          <span>Periods Where Rebalancing Added Value</span>
          <strong className="mono positive">
            {rows.filter((r) => r.should_rebalance || (numberLike(r.net_value_bps ?? r.net_value) ?? 0) > threshold).length}/{rows.length}
          </strong>
        </div>
        <div className="rcb-card">
          <span>Average Net Value per Rebalance</span>
          <strong className={`mono ${(chartData.reduce((s, r) => s + (r.net_value > 0 ? r.net_value : 0), 0) / Math.max(1, chartData.filter((r) => r.net_value > 0).length)) >= 0 ? "positive" : "negative"}`}>
            {formatValue(chartData.reduce((s, r) => s + (r.net_value > 0 ? r.net_value : 0), 0) / Math.max(1, chartData.filter((r) => r.net_value > 0).length))} bps
          </strong>
        </div>
      </div>

      <div className="rcb-threshold-control">
        <span>Net value threshold for rebalancing decision</span>
        <input
          type="range"
          min={-20}
          max={50}
          step={1}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
        />
        <b className="mono">{threshold} bps</b>
      </div>

      <ResponsiveContainer height={400} width="100%">
        <ComposedChart data={chartData} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="date" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeOpacity={0.5} />
          <ReferenceLine y={threshold} stroke={TOKENS.amber} strokeDasharray="5 4" label={{ value: "Threshold", fill: TOKENS.amber, fontSize: 9, position: "insideTopRight" }} />
          {/* Rebalance event markers */}
          {chartData.filter((r) => r.rebalance).map((r, i) => (
            <ReferenceLine key={i} x={r.date} stroke={TOKENS.green} strokeWidth={1} strokeOpacity={0.4} />
          ))}
          <Bar dataKey="sharpe_benefit" name="Sharpe Benefit" fill={TOKENS.teal} fillOpacity={0.7} />
          <Bar dataKey="cost_bps" name="Cost (bps)" fill={TOKENS.red} fillOpacity={0.6} />
          <Line dataKey="net_value" name="Net Value (bps)" stroke={TOKENS.accent} strokeWidth={2.5} dot={false} type="monotone" />
        </ComposedChart>
      </ResponsiveContainer>

      <DataTable data={rows} config={{ colorBySign: true }} />
    </div>
  );
}
```

**Factor Exposure Profile Pushed Directly into F02:**

This is a state-management bridge between F10 optimizer output and F02's portfolio input. In your application state layer (or via your Zustand/React Context store), when the optimizer produces an optimal weight vector, expose a button that pushes it to F02:

```javascript
// In your optimizer output section, add a "Push to F02" button:
function OptimizerWeightExport({ data, onPushToF02 }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const weightsAsHoldings = useMemo(() =>
    rows.map((r) => ({ ticker: r.factor || r.asset || r.name, weight: numberLike(r.weight ?? r.optimal_weight) ?? 0 })).filter((r) => r.ticker),
  [rows]);

  if (!weightsAsHoldings.length) return null;

  return (
    <div className="optimizer-export">
      <button
        className="push-to-f02-btn"
        onClick={() => onPushToF02?.(weightsAsHoldings)}
        type="button"
      >
        <CheckCircle2 size={14} />
        Push Optimal Weights to F02 Portfolio X-Ray
      </button>
      <small>This will pre-populate F02's portfolio input with the factor-optimal weights for full exposure decomposition and DDQ attribution.</small>
    </div>
  );
}
```

In your `CustomFeaturePage` state management, add cross-feature state sharing:

```javascript
// In your global state store or context:
const [sharedPortfolioHoldings, setSharedPortfolioHoldings] = useState(null);

// When F10 pushes weights:
function handlePushToF02(holdings) {
  setSharedPortfolioHoldings(holdings);
  toast.success("Optimal weights loaded into F02 Portfolio X-Ray. Navigate to Feature 02.");
  // Optionally navigate:
  window.location.href = "/labs/factors-v2/feature-02";
}

// In F02's GroupedInputForm, pre-populate holdings field:
const holdingsDefaultValue = sharedPortfolioHoldings ? JSON.stringify(sharedPortfolioHoldings) : feature.defaults?.holdings;
```

CSS:

```javascript
const rebalancingCostStyles = `
  .rebalancing-cost-benefit { display: grid; gap: 14px; }
  .rcb-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .rcb-card { border: 1px solid ${TOKENS.border}; background: ${TOKENS.elevated}; border-radius: 8px; padding: 12px 14px; display: grid; gap: 4px; }
  .rcb-card span { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; font-weight: 800; }
  .rcb-card strong { font-size: 24px; }
  .rcb-threshold-control { display: flex; align-items: center; gap: 10px; }
  .rcb-threshold-control span { color: ${TOKENS.muted}; font-size: 11px; }
  .rcb-threshold-control input { flex: 1; accent-color: ${TOKENS.accent}; }
  .rcb-threshold-control b { font-size: 12px; font-family: "Quant360 Mono","JetBrains Mono",monospace; color: ${TOKENS.amber}; white-space: nowrap; }
  .optimizer-export { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; border: 1px solid rgba(34,197,94,.3); background: rgba(34,197,94,.06); border-radius: 8px; padding: 12px 14px; margin-top: 8px; }
  .push-to-f02-btn { min-height: 36px; padding: 0 14px; border: 1px solid rgba(34,197,94,.4); background: rgba(34,197,94,.1); color: ${TOKENS.green}; border-radius: 7px; font-size: 12px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 8px; }
  .optimizer-export small { color: ${TOKENS.secondary}; font-size: 11px; line-height: 1.4; }
`;
```

---

## FEATURE 11: Stress Testing — Fully Polished Reverse Stress Narrative and Contagion IRF

### Reverse Stress Plain-English Narrative

```javascript
function ReverseStressNarrative({ data }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const first = rows[0] || {};
  const lossTarget = numberLike(first.loss_target_pct ?? first.portfolio_loss_pct);
  const historicalProb = numberLike(first.historical_probability_pct ?? first.probability_pct);
  const factorShocks = useMemo(() =>
    Object.entries(first)
      .filter(([k]) => /^factor_shock_|_shock_bps/.test(k))
      .map(([k, v]) => ({ factor: k.replace(/^factor_shock_|_shock_bps$/, ""), shock: numberLike(v) }))
      .filter((s) => s.shock != null)
      .sort((a, b) => Math.abs(b.shock) - Math.abs(a.shock))
      .slice(0, 5),
  [first]);

  // Macro analog
  const macroAnalog = first.macro_analog || first.closest_historical_analog;

  return (
    <div className="reverse-stress-narrative">
      {/* Loss threshold summary */}
      <div className="rsn-target">
        <span>Portfolio Loss Target</span>
        <strong className="mono negative">{lossTarget != null ? `${lossTarget >= 0 ? "-" : ""}${Math.abs(lossTarget).toFixed(1)}%` : "—"}</strong>
        {historicalProb != null ? (
          <div className="rsn-prob">
            <i style={{ background: historicalProb >= 10 ? TOKENS.amber : TOKENS.red }} />
            <span>
              This scenario occurs in approximately <b>{historicalProb.toFixed(1)}%</b> of trailing quarterly windows — historically
              {historicalProb >= 10 ? " an elevated but plausible tail event" : historicalProb >= 2 ? " a rare but precedented stress scenario" : " an extreme tail event without close historical parallel"}.
            </span>
          </div>
        ) : null}
      </div>

      {/* Factor shock requirements */}
      <div className="rsn-shocks">
        <div className="rsn-shocks-header">Required Factor Shock Vector to Produce This Loss</div>
        {factorShocks.map((s, i) => {
          const color = s.shock < 0 ? TOKENS.red : TOKENS.green;
          const magnitude = Math.abs(s.shock);
          const maxMag = Math.max(...factorShocks.map((x) => Math.abs(x.shock)));
          return (
            <div key={s.factor} className="rsn-shock-row">
              <span>{titleize(s.factor)}</span>
              <div className="rsn-shock-bar">
                <div style={{ width: `${(magnitude / maxMag) * 100}%`, background: color }} />
              </div>
              <b className="mono" style={{ color }}>
                {s.shock >= 0 ? "+" : ""}{s.shock.toFixed(0)} bps
              </b>
            </div>
          );
        })}
      </div>

      {/* Plain English narrative paragraph */}
      <div className="rsn-narrative">
        <div className="rsn-narrative-label">Plain-Language Scenario Description</div>
        <p>
          {lossTarget != null && factorShocks.length >= 2 ? (
            <>
              This portfolio loses{" "}
              <strong className="negative">{Math.abs(lossTarget).toFixed(1)}%</strong> if{" "}
              {factorShocks.slice(0, 3).map((s, i) => (
                <span key={s.factor}>
                  {i > 0 ? (i === factorShocks.slice(0, 3).length - 1 ? " and " : ", ") : ""}
                  {titleize(s.factor)} returns{" "}
                  <strong className={s.shock < 0 ? "negative" : "positive"}>
                    {s.shock >= 0 ? "+" : ""}{(s.shock / 100).toFixed(1)}%
                  </strong>
                </span>
              ))}{" "}
              simultaneously
              {historicalProb != null ? `, a combination historically observed in approximately ${historicalProb.toFixed(1)}% of rolling quarterly windows.` : "."}
              {macroAnalog ? ` The closest historical analog is ${macroAnalog}.` : ""}
              {" "}The primary driver of loss is{" "}
              <strong>{titleize(factorShocks[0]?.factor)}</strong> exposure, which accounts for the largest single contribution. Hedging this factor exposure would reduce the scenario loss substantially.
            </>
          ) : (
            <span className="rsn-placeholder">Run the reverse stress computation to generate the factor shock vector and narrative. Set a portfolio loss threshold above to begin.</span>
          )}
        </p>
      </div>

      {/* Macro analog context */}
      {macroAnalog ? (
        <div className="rsn-analog">
          <div className="rsn-analog-label">Closest Historical Analog</div>
          <div className="rsn-analog-content">
            <strong>{macroAnalog}</strong>
            {first.analog_distance != null ? (
              <span>Mahalanobis distance: <b className="mono">{numberLike(first.analog_distance)?.toFixed(2)}</b></span>
            ) : null}
            {first.analog_factor_return != null ? (
              <span>Factor return in analog: <b className={`mono ${numberLike(first.analog_factor_return) >= 0 ? "positive" : "negative"}`}>{(numberLike(first.analog_factor_return) * 100).toFixed(1)}%</b></span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Hedging recommendation */}
      {first.hedge_factor && (
        <div className="rsn-hedge">
          <CheckCircle2 size={14} />
          <div>
            <strong>Recommended Hedge</strong>
            <span>
              Short <b>{titleize(first.hedge_factor)}</b> at a ratio of <b className="mono">{formatValue(first.hedge_ratio)}</b>.
              Estimated hedging cost: <b className="mono">{formatValue(first.hedge_cost_bps)} bps</b>.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Contagion Impulse Response Chart:**

```javascript
function ContagionIRFChart({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ shocked_factor: "momentum_12_1", affected_factor: "quality_roe", horizon_1: -0.12, horizon_5: -0.08, horizon_10: -0.04, horizon_21: -0.01, ci_low_21: -0.06, ci_high_21: 0.04 }, ...]

  const shockedFactors = useMemo(() => [...new Set(rows.map((r) => r.shocked_factor || r.source_factor))], [rows]);
  const [selectedShock, setSelectedShock] = useState(shockedFactors[0]);

  const filteredRows = useMemo(() =>
    rows.filter((r) => (r.shocked_factor || r.source_factor) === selectedShock),
  [rows, selectedShock]);

  const horizons = [1, 5, 10, 21];

  // Build chart data: one row per horizon, one column per affected factor
  const affectedFactors = useMemo(() => [...new Set(filteredRows.map((r) => r.affected_factor || r.target_factor))], [filteredRows]);
  const chartData = useMemo(() => horizons.map((h) => {
    const entry = { horizon: h };
    filteredRows.forEach((r) => {
      const af = r.affected_factor || r.target_factor;
      entry[af] = numberLike(r[`horizon_${h}`] ?? r[`h${h}`]);
    });
    return entry;
  }), [filteredRows]);

  return (
    <div className="contagion-irf">
      {/* Shock factor selector */}
      <div className="irf-shock-selector">
        <span>Shocked Factor</span>
        <div className="pro-chips">
          {shockedFactors.map((f) => (
            <button
              key={f}
              className={selectedShock === f ? "active" : ""}
              onClick={() => setSelectedShock(f)}
              type="button"
            >
              {titleize(f)}
            </button>
          ))}
        </div>
      </div>

      <div className="irf-description">
        Impulse response of all other factors to a 1-standard-deviation shock in <strong>{titleize(selectedShock)}</strong>, with 90% bootstrap confidence bands.
      </div>

      <ResponsiveContainer height={400} width="100%">
        <LineChart data={chartData} margin={{ top: 14, right: 28, left: 6, bottom: 12 }}>
          <CartesianGrid stroke={TOKENS.grid} strokeOpacity={0.45} vertical={false} />
          <XAxis dataKey="horizon" label={{ value: "Days After Shock", fill: TOKENS.secondary, fontSize: 10, position: "insideBottom", offset: -8 }} {...axisProps} />
          <YAxis label={{ value: "Factor Return Response", fill: TOKENS.secondary, fontSize: 10, angle: -90, position: "insideLeft" }} {...axisProps} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeDasharray="3 5" strokeOpacity={0.55} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ color: TOKENS.secondary, fontSize: 11 }} />
          {affectedFactors.map((af, i) => (
            <Line
              key={af}
              dataKey={af}
              stroke={SERIES[i % SERIES.length]}
              strokeWidth={2}
              dot={{ r: 5, fill: SERIES[i % SERIES.length], strokeWidth: 0 }}
              type="monotone"
              name={titleize(af)}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Summary table: which factors are most contagion-sensitive */}
      <div className="irf-contagion-summary">
        <div className="irf-summary-label">Contagion Sensitivity at 5-Day Horizon</div>
        {filteredRows
          .map((r) => ({ factor: r.affected_factor || r.target_factor, response: numberLike(r.horizon_5 ?? r.h5) ?? 0 }))
          .sort((a, b) => Math.abs(b.response) - Math.abs(a.response))
          .map((item, i) => (
            <div key={i} className="irf-contagion-row">
              <span>{titleize(item.factor)}</span>
              <div className="irf-bar">
                <div style={{ width: `${Math.min(100, Math.abs(item.response) * 500)}%`, background: item.response < 0 ? TOKENS.red : TOKENS.green, marginLeft: item.response < 0 ? "auto" : 0 }} />
              </div>
              <b className={`mono ${item.response < 0 ? "negative" : "positive"}`}>
                {item.response >= 0 ? "+" : ""}{(item.response * 100).toFixed(1)}%
              </b>
            </div>
          ))}
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "reverseStressNarrative") return <ReverseStressNarrative data={data} />;
if (section.chartType === "contagionIRF") return <ContagionIRFChart data={data} config={section.config} />;
```

CSS:

```javascript
const stressStyles = `
  .reverse-stress-narrative { display: grid; gap: 14px; }
  .rsn-target { border: 1px solid rgba(239,68,68,.3); background: rgba(239,68,68,.06); border-radius: 8px; padding: 14px 16px; display: grid; gap: 8px; }
  .rsn-target span { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .rsn-target strong { font-size: 36px; font-weight: 800; }
  .rsn-prob { display: flex; align-items: flex-start; gap: 8px; }
  .rsn-prob i { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; margin-top: 3px; }
  .rsn-prob span { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.5; }
  .rsn-prob b { color: ${TOKENS.text}; }
  .rsn-shocks { border: 1px solid ${TOKENS.border}; border-radius: 8px; padding: 12px; background: ${TOKENS.elevated}; display: grid; gap: 8px; }
  .rsn-shocks-header { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .rsn-shock-row { display: grid; grid-template-columns: 160px 1fr 80px; gap: 10px; align-items: center; }
  .rsn-shock-row span { color: ${TOKENS.secondary}; font-size: 12px; }
  .rsn-shock-bar { height: 8px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; }
  .rsn-shock-bar div { height: 100%; border-radius: 999px; }
  .rsn-narrative { border: 1px solid ${TOKENS.borderSubtle}; background: rgba(13,17,23,.7); border-radius: 8px; padding: 16px; }
  .rsn-narrative-label { color: ${TOKENS.amber}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; margin-bottom: 10px; }
  .rsn-narrative p { margin: 0; color: ${TOKENS.secondary}; font-size: 13px; line-height: 1.7; }
  .rsn-narrative strong { color: ${TOKENS.text}; }
  .rsn-placeholder { color: ${TOKENS.textDisabled}; font-style: italic; }
  .rsn-analog { border: 1px solid rgba(245,164,0,.25); background: rgba(245,164,0,.05); border-radius: 8px; padding: 12px 14px; display: grid; gap: 6px; }
  .rsn-analog-label { color: ${TOKENS.amber}; font-size: 9px; text-transform: uppercase; letter-spacing: .12em; font-weight: 800; }
  .rsn-analog-content { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
  .rsn-analog-content strong { color: ${TOKENS.text}; font-size: 14px; }
  .rsn-analog-content span { color: ${TOKENS.secondary}; font-size: 12px; }
  .rsn-hedge { display: flex; align-items: flex-start; gap: 10px; border: 1px solid rgba(34,197,94,.28); background: rgba(34,197,94,.06); border-radius: 8px; padding: 12px 14px; color: ${TOKENS.green}; }
  .rsn-hedge svg { flex-shrink: 0; margin-top: 2px; }
  .rsn-hedge strong { display: block; font-size: 12px; margin-bottom: 4px; }
  .rsn-hedge span { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.45; }
  .rsn-hedge b { color: ${TOKENS.text}; }
  .contagion-irf { display: grid; gap: 14px; }
  .irf-shock-selector { display: grid; gap: 6px; }
  .irf-shock-selector span { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .irf-description { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.5; }
  .irf-description strong { color: ${TOKENS.accent}; }
  .irf-contagion-summary { border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 12px; background: ${TOKENS.elevated}; display: grid; gap: 8px; }
  .irf-summary-label { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .irf-contagion-row { display: grid; grid-template-columns: 160px 1fr 80px; gap: 10px; align-items: center; }
  .irf-contagion-row span { color: ${TOKENS.secondary}; font-size: 12px; }
  .irf-bar { height: 8px; background: ${TOKENS.active}; border-radius: 999px; overflow: hidden; display: flex; }
  .irf-bar div { height: 100%; border-radius: 999px; }
`;
```

---

## FEATURE 12: Factor DNA — Auto-Classifier Explanation Tree and Overlay Comparison

### Auto-Classifier Explanation Tree

```javascript
function AutoClassifierExplainTree({ data, config = {} }) {
  const [expanded, setExpanded] = useState({});
  const rows = useMemo(() => rowsFrom(data), [data]);

  // rows shape: [{ class: "Behavioral Factor", probability: 0.72, key_drivers: [...], evidence_for: [...], evidence_against: [...] }, ...]
  const dominant = useMemo(() => [...rows].sort((a, b) => (numberLike(b.probability) ?? 0) - (numberLike(a.probability) ?? 0))[0], [rows]);

  const classColors = {
    "Risk Factor": TOKENS.teal,
    "Behavioral Factor": TOKENS.amber,
    "Structural Factor": TOKENS.purple,
    "Data-Mining Artifact": TOKENS.red,
  };

  return (
    <div className="classifier-tree">
      {/* Dominant classification */}
      <div className="classifier-dominant" style={{ borderColor: `${classColors[dominant?.class] || TOKENS.accent}50` }}>
        <div className="classifier-dominant-badge" style={{ background: classColors[dominant?.class] || TOKENS.accent }}>
          {(numberLike(dominant?.probability) * 100 || 0).toFixed(0)}% Confidence
        </div>
        <strong>{dominant?.class || "Unclassified"}</strong>
        <p>{dominant?.description || {
          "Risk Factor": "This factor earns its return by bearing systematic risk. It is expected to persist because investors require compensation for the risk it represents. Characterized by long half-life, low crowding susceptibility, and stable regime behavior.",
          "Behavioral Factor": "This factor exploits predictable investor biases. The premium may erode after academic publication as arbitrageurs learn to trade against it. Monitor for IC decay acceleration post-2015.",
          "Structural Factor": "This factor exploits market frictions such as transaction costs, regulatory constraints, or index mechanics. These factors tend to be highly stable because the friction persists.",
          "Data-Mining Artifact": "The statistical evidence for this factor is fragile. IC collapses out-of-sample, the purity score is low, and the factor's performance does not generalize across market environments. Do not trade.",
        }[dominant?.class] || ""}</p>
      </div>

      {/* Probability bar */}
      <div className="classifier-prob-bar">
        {rows.map((row, i) => {
          const prob = numberLike(row.probability) ?? 0;
          const color = classColors[row.class] || SERIES[i % SERIES.length];
          return (
            <div
              key={i}
              className="classifier-prob-segment"
              style={{ width: `${prob * 100}%`, background: color }}
              title={`${row.class}: ${(prob * 100).toFixed(0)}%`}
            />
          );
        })}
      </div>
      <div className="classifier-prob-legend">
        {rows.map((row, i) => (
          <div key={i} className="classifier-prob-item">
            <i style={{ background: classColors[row.class] || SERIES[i % SERIES.length] }} />
            <span>{row.class}</span>
            <b className="mono">{((numberLike(row.probability) ?? 0) * 100).toFixed(0)}%</b>
          </div>
        ))}
      </div>

      {/* Decision tree nodes */}
      <div className="classifier-tree-body">
        {rows.map((row, i) => {
          const isOpen = expanded[i];
          const prob = numberLike(row.probability) ?? 0;
          const color = classColors[row.class] || SERIES[i % SERIES.length];
          const evidence_for = Array.isArray(row.evidence_for) ? row.evidence_for : [];
          const evidence_against = Array.isArray(row.evidence_against) ? row.evidence_against : [];

          return (
            <div key={i} className={`classifier-node ${row === dominant ? "dominant-node" : ""}`} style={{ borderColor: `${color}40` }}>
              <button
                className="classifier-node-header"
                onClick={() => setExpanded((prev) => ({ ...prev, [i]: !isOpen }))}
                type="button"
              >
                <i style={{ background: color }} />
                <span style={{ color }}>{row.class}</span>
                <b className="mono">{(prob * 100).toFixed(0)}%</b>
                <ChevronDown size={13} style={{ transform: isOpen ? "rotate(180deg)" : "none", transition: "transform 200ms ease", color: TOKENS.secondary }} />
              </button>

              {isOpen ? (
                <div className="classifier-node-body">
                  {evidence_for.length ? (
                    <div className="classifier-evidence">
                      <div className="ce-label positive">Evidence for this classification</div>
                      {evidence_for.map((ev, j) => (
                        <div key={j} className="ce-item positive">
                          <CheckCircle2 size={12} />
                          <span>{ev}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {evidence_against.length ? (
                    <div className="classifier-evidence">
                      <div className="ce-label negative">Evidence against</div>
                      {evidence_against.map((ev, j) => (
                        <div key={j} className="ce-item negative">
                          <X size={12} />
                          <span>{ev}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {Array.isArray(row.key_drivers) && row.key_drivers.length ? (
                    <div className="classifier-drivers">
                      <div className="cd-label">Key diagnostic drivers</div>
                      {row.key_drivers.map((driver, j) => (
                        <div key={j} className="cd-item">
                          <span>{driver.metric || driver.name}</span>
                          <b className={`mono ${driver.direction === "positive" ? "positive" : "negative"}`}>
                            {formatValue(driver.value)}
                          </b>
                          <small>{driver.interpretation}</small>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**Factor DNA Overlay Comparison:**

```javascript
function FactorDNAOverlay({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ factor: "momentum_12_1", ic: 78, icir: 65, ... }, { factor: "value_pb", ic: 52, ... }]
  const axes = ["ic", "icir", "half_life_score", "crowding_score_inv", "sector_concentration_inv", "regime_dependence_inv", "correlation_to_nearest_inv", "purity_score"];
  const axisLabels = { ic: "IC", icir: "ICIR", half_life_score: "Persistence", crowding_score_inv: "Uncrowded", sector_concentration_inv: "Diversified", regime_dependence_inv: "Regime-Stable", correlation_to_nearest_inv: "Orthogonal", purity_score: "Purity" };

  const [primary, setPrimary] = useState(rows[0]?.factor || rows[0]?.name);
  const [comparisons, setComparisons] = useState(() => rows.slice(1, 3).map((r) => r.factor || r.name));

  const activeRows = [primary, ...comparisons].filter(Boolean).map((f) => rows.find((r) => (r.factor || r.name) === f)).filter(Boolean);

  const chartData = axes.map((axis) => {
    const entry = { axis: axisLabels[axis] };
    activeRows.forEach((row) => {
      entry[row.factor || row.name] = numberLike(row[axis]) ?? 0;
    });
    return entry;
  });

  const allFactors = rows.map((r) => r.factor || r.name);

  return (
    <div className="dna-overlay">
      {/* Primary factor selector */}
      <div className="dna-selector-row">
        <div className="dna-selector-group">
          <span>Primary factor</span>
          <div className="pro-chips">
            {allFactors.map((f) => (
              <button
                key={f}
                className={primary === f ? "active" : ""}
                onClick={() => setPrimary(f)}
                type="button"
              >
                {titleize(f)}
              </button>
            ))}
          </div>
        </div>
        <div className="dna-selector-group">
          <span>Compare with (up to 4)</span>
          <div className="pro-chips">
            {allFactors.filter((f) => f !== primary).map((f) => (
              <button
                key={f}
                className={comparisons.includes(f) ? "active" : ""}
                onClick={() => setComparisons((prev) =>
                  prev.includes(f) ? prev.filter((x) => x !== f) : prev.length < 4 ? [...prev, f] : prev
                )}
                type="button"
              >
                {titleize(f)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Radar overlay */}
      <ResponsiveContainer height={460} width="100%">
        <RadarChart data={chartData} outerRadius="72%">
          <PolarGrid stroke={TOKENS.grid} strokeOpacity={0.5} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={{ fill: TOKENS.secondary, fontSize: 9 }} tickCount={5} />
          {activeRows.map((row, i) => (
            <Radar
              key={row.factor || row.name}
              dataKey={row.factor || row.name}
              name={titleize(row.factor || row.name)}
              fill={SERIES[i % SERIES.length]}
              fillOpacity={i === 0 ? 0.2 : 0.1}
              stroke={SERIES[i % SERIES.length]}
              strokeWidth={i === 0 ? 3 : 1.5}
              strokeDasharray={i > 0 ? "5 4" : undefined}
            />
          ))}
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ color: TOKENS.secondary, fontSize: 11 }} />
        </RadarChart>
      </ResponsiveContainer>

      {/* Score comparison table */}
      <div className="table-scroll">
        <table className="f2-table">
          <thead>
            <tr>
              <th><button type="button">Metric</button></th>
              {activeRows.map((row, i) => (
                <th key={i} style={{ color: SERIES[i % SERIES.length] }}>
                  <button type="button">{titleize(row.factor || row.name)}</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {axes.map((axis) => (
              <tr key={axis}>
                <td style={{ textAlign: "left" }}>{axisLabels[axis]}</td>
                {activeRows.map((row, i) => {
                  const v = numberLike(row[axis]) ?? 0;
                  return (
                    <td key={i} className="mono" style={{ color: v >= 70 ? TOKENS.green : v >= 40 ? TOKENS.text : TOKENS.red }}>
                      {v.toFixed(0)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "classifierTree") return <AutoClassifierExplainTree data={data} config={section.config} />;
if (section.chartType === "dnaOverlay") return <FactorDNAOverlay data={data} config={section.config} />;
```

CSS:

```javascript
const dnaStyles = `
  .classifier-tree { display: grid; gap: 14px; }
  .classifier-dominant { border: 1px solid; border-radius: 10px; padding: 18px; position: relative; overflow: hidden; }
  .classifier-dominant-badge { position: absolute; top: 12px; right: 12px; color: ${TOKENS.panel}; font-size: 9px; font-weight: 900; letter-spacing: .12em; border-radius: 4px; padding: 4px 7px; }
  .classifier-dominant strong { font-size: 22px; display: block; margin-bottom: 8px; }
  .classifier-dominant p { color: ${TOKENS.secondary}; font-size: 12px; line-height: 1.6; margin: 0; max-width: 760px; }
  .classifier-prob-bar { display: flex; height: 10px; border-radius: 999px; overflow: hidden; gap: 2px; }
  .classifier-prob-segment { height: 100%; transition: width .5s cubic-bezier(.4,0,.2,1); }
  .classifier-prob-legend { display: flex; flex-wrap: wrap; gap: 10px; }
  .classifier-prob-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: ${TOKENS.secondary}; }
  .classifier-prob-item i { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .classifier-prob-item b { font-size: 12px; color: ${TOKENS.text}; }
  .classifier-tree-body { display: grid; gap: 8px; }
  .classifier-node { border: 1px solid; border-radius: 8px; overflow: hidden; }
  .dominant-node { box-shadow: 0 0 0 1px rgba(245,164,0,.15); }
  .classifier-node-header { width: 100%; display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: transparent; border: 0; cursor: pointer; text-align: left; }
  .classifier-node-header:hover { background: ${TOKENS.elevated}; }
  .classifier-node-header i { width: 10px; height: 10px; border-radius: 999px; flex-shrink: 0; }
  .classifier-node-header span { font-size: 13px; font-weight: 700; flex: 1; }
  .classifier-node-header b { font-size: 13px; font-family: "Quant360 Mono","JetBrains Mono",monospace; }
  .classifier-node-body { padding: 0 14px 14px; display: grid; gap: 10px; }
  .classifier-evidence { display: grid; gap: 6px; }
  .ce-label { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }
  .ce-label.positive { color: ${TOKENS.green}; }
  .ce-label.negative { color: ${TOKENS.red}; }
  .ce-item { display: flex; align-items: flex-start; gap: 7px; color: ${TOKENS.secondary}; font-size: 11px; line-height: 1.45; }
  .ce-item.positive svg { color: ${TOKENS.green}; flex-shrink: 0; margin-top: 1px; }
  .ce-item.negative svg { color: ${TOKENS.red}; flex-shrink: 0; margin-top: 1px; }
  .classifier-drivers { display: grid; gap: 8px; border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 10px; }
  .cd-label { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; color: ${TOKENS.amber}; }
  .cd-item { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: start; }
  .cd-item span { color: ${TOKENS.text}; font-size: 12px; }
  .cd-item b { font-size: 12px; }
  .cd-item small { grid-column: 1 / -1; color: ${TOKENS.muted}; font-size: 11px; line-height: 1.4; }
  .dna-overlay { display: grid; gap: 14px; }
  .dna-selector-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .dna-selector-group { display: grid; gap: 6px; }
  .dna-selector-group span { color: ${TOKENS.muted}; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .13em; }
`;
```

---

## FEATURE 13: Signal Monitor — Full Signal Recovery Tracker and Alert Lifecycle

### Signal Recovery Tracker

```javascript
function SignalRecoveryTracker({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  // rows shape: [{ factor: "momentum_12_1", alert_triggered_date: "2025-07-15", days_since_alert: 42, ic_at_alert: 0.021, ic_current: 0.048, ic_longrun: 0.068, health_at_alert: 28, health_current: 61, recovery_status: "recovering"|"deteriorating"|"recovered"|"stale", ... }]

  const statusColors = {
    recovered: TOKENS.green,
    recovering: TOKENS.amber,
    deteriorating: TOKENS.red,
    stale: TOKENS.muted,
  };

  return (
    <div className="recovery-tracker">
      <div className="recovery-summary-grid">
        {[
          { label: "Recovered", key: "recovered", color: TOKENS.green },
          { label: "Recovering", key: "recovering", color: TOKENS.amber },
          { label: "Deteriorating", key: "deteriorating", color: TOKENS.red },
        ].map((status) => (
          <div key={status.key} className="recovery-summary-card" style={{ borderColor: `${status.color}40` }}>
            <span style={{ color: status.color }}>{status.label}</span>
            <strong style={{ color: status.color }}>
              {rows.filter((r) => r.recovery_status === status.key).length}
            </strong>
          </div>
        ))}
      </div>

      {rows.map((row, i) => {
        const status = row.recovery_status || "stale";
        const color = statusColors[status] || TOKENS.muted;
        const icAtAlert = numberLike(row.ic_at_alert);
        const icCurrent = numberLike(row.ic_current);
        const icLongrun = numberLike(row.ic_longrun);
        const healthAtAlert = numberLike(row.health_at_alert);
        const healthCurrent = numberLike(row.health_current);
        const daysSince = numberLike(row.days_since_alert);

        // Build mini IC recovery curve: alert, midpoints, current
        const recoveryCurveData = [
          { t: 0, ic: icAtAlert, label: "Alert" },
          ...(row.ic_history_since_alert ? rowsFrom(row.ic_history_since_alert) : [{ t: daysSince / 2, ic: (icAtAlert + icCurrent) / 2, label: "Mid" }]),
          { t: daysSince ?? 0, ic: icCurrent, label: "Now" },
        ].filter((p) => p.ic != null);

        return (
          <div key={i} className="recovery-card" style={{ borderLeft: `3px solid ${color}` }}>
            <div className="recovery-card-header">
              <div className="recovery-factor-name">{titleize(row.factor || row.label)}</div>
              <div className="recovery-status-badge" style={{ background: `${color}20`, color, borderColor: `${color}40` }}>
                {status.toUpperCase()}
              </div>
              <div className="recovery-days mono">{daysSince != null ? `${daysSince}d since alert` : ""}</div>
            </div>

            <div className="recovery-metrics">
              {/* IC at alert vs current vs long-run */}
              <div className="recovery-metric">
                <span>IC at Alert</span>
                <b className="mono negative">{icAtAlert != null ? icAtAlert.toFixed(3) : "—"}</b>
              </div>
              <div className="recovery-metric">
                <span>IC Now</span>
                <b className={`mono ${icCurrent != null && icAtAlert != null && icCurrent > icAtAlert ? "positive" : "negative"}`}>
                  {icCurrent != null ? icCurrent.toFixed(3) : "—"}
                </b>
              </div>
              <div className="recovery-metric">
                <span>Long-Run IC</span>
                <b className="mono secondary">{icLongrun != null ? icLongrun.toFixed(3) : "—"}</b>
              </div>
              <div className="recovery-metric">
                <span>Health Score</span>
                <b className={`mono ${healthCurrent != null && healthCurrent > 60 ? "positive" : healthCurrent > 40 ? "" : "negative"}`}>
                  {healthAtAlert != null ? `${healthAtAlert}` : "—"} → {healthCurrent != null ? healthCurrent : "—"}
                </b>
              </div>
            </div>

            {/* Mini recovery curve */}
            {recoveryCurveData.length >= 2 ? (
              <div className="recovery-mini-chart">
                <ResponsiveContainer height={80} width="100%">
                  <LineChart data={recoveryCurveData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <ReferenceLine y={icLongrun ?? 0} stroke={TOKENS.secondary} strokeDasharray="3 4" strokeOpacity={0.5} />
                    <ReferenceLine y={0} stroke={TOKENS.red} strokeDasharray="2 4" strokeOpacity={0.4} />
                    <Line dataKey="ic" stroke={color} strokeWidth={2} dot={false} type="monotone" />
                    <YAxis hide />
                    <XAxis dataKey="t" hide />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
```

**Full Alert Lifecycle with Resolved/Open States:**

The `AlertFeed` component above already handles this. Extend it with a lifecycle state machine display:

```javascript
function AlertLifecycleView({ data }) {
  const alerts = useMemo(() => rowsFrom(data), [data]);
  const [selectedAlert, setSelectedAlert] = useState(null);

  const STAGES = ["triggered", "acknowledged", "monitoring", "resolved"];

  return (
    <div className="alert-lifecycle">
      <div className="alert-lifecycle-list">
        {alerts.map((alert, i) => {
          const stage = alert.lifecycle_stage || (alert.resolved ? "resolved" : alert.acknowledged ? "monitoring" : "triggered");
          const stageIndex = STAGES.indexOf(stage);
          const pct = numberLike(alert.percentile ?? alert.current_pct);
          const color = pct >= 70 ? TOKENS.red : pct <= 30 ? TOKENS.green : TOKENS.amber;

          return (
            <div
              key={i}
              className={`alc-row ${selectedAlert === i ? "selected" : ""}`}
              onClick={() => setSelectedAlert(selectedAlert === i ? null : i)}
            >
              <i className="alc-dot" style={{ background: color }} />
              <div className="alc-content">
                <strong>{titleize(alert.factor || alert.label)}</strong>
                <span>{alert.message || `Factor crossed ${alert.threshold}th percentile`}</span>
              </div>
              {/* Lifecycle progress bar */}
              <div className="alc-stages">
                {STAGES.map((s, si) => (
                  <div
                    key={s}
                    className={`alc-stage ${si <= stageIndex ? "complete" : ""} ${si === stageIndex ? "current" : ""}`}
                    title={s}
                  >
                    {si < STAGES.length - 1 ? <div className="alc-connector" /> : null}
                  </div>
                ))}
              </div>
              <div className="alc-stage-label">{stage}</div>
            </div>
          );
        })}
      </div>

      {/* Expanded alert detail */}
      {selectedAlert != null && alerts[selectedAlert] ? (
        <div className="alc-detail">
          <div className="alc-detail-header">Alert Detail: {titleize(alerts[selectedAlert].factor || alerts[selectedAlert].label)}</div>
          <DataTable data={[alerts[selectedAlert]]} />
        </div>
      ) : null}
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "signalRecoveryTracker") return <SignalRecoveryTracker data={data} config={section.config} />;
if (section.chartType === "alertLifecycle") return <AlertLifecycleView data={data} />;
```

CSS:

```javascript
const signalMonitorStyles = `
  .recovery-tracker { display: grid; gap: 12px; }
  .recovery-summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .recovery-summary-card { border: 1px solid; border-radius: 7px; padding: 10px 12px; display: grid; gap: 3px; background: ${TOKENS.elevated}; }
  .recovery-summary-card span { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }
  .recovery-summary-card strong { font-size: 24px; }
  .recovery-card { border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 12px; background: ${TOKENS.elevated}; display: grid; gap: 10px; }
  .recovery-card-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .recovery-factor-name { font-size: 13px; font-weight: 700; color: ${TOKENS.text}; flex: 1; }
  .recovery-status-badge { border: 1px solid; border-radius: 4px; padding: 3px 8px; font-size: 9px; font-weight: 900; letter-spacing: .1em; }
  .recovery-days { color: ${TOKENS.muted}; font-size: 10px; }
  .recovery-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .recovery-metric { display: grid; gap: 2px; }
  .recovery-metric span { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .1em; }
  .recovery-metric b { font-size: 13px; }
  .recovery-mini-chart { border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 6px; }
  .alert-lifecycle { display: grid; gap: 10px; }
  .alert-lifecycle-list { display: grid; gap: 8px; }
  .alc-row { display: grid; grid-template-columns: 10px 1fr auto auto; gap: 10px; align-items: center; border: 1px solid ${TOKENS.borderSubtle}; background: ${TOKENS.elevated}; border-radius: 7px; padding: 10px 12px; cursor: pointer; transition: border-color .15s ease; }
  .alc-row.selected { border-color: rgba(245,164,0,.4); }
  .alc-dot { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
  .alc-content { display: grid; gap: 2px; }
  .alc-content strong { color: ${TOKENS.text}; font-size: 12px; }
  .alc-content span { color: ${TOKENS.secondary}; font-size: 11px; }
  .alc-stages { display: flex; align-items: center; gap: 0; }
  .alc-stage { width: 10px; height: 10px; border-radius: 999px; border: 2px solid ${TOKENS.border}; background: ${TOKENS.elevated}; position: relative; flex-shrink: 0; }
  .alc-stage.complete { background: ${TOKENS.accent}; border-color: ${TOKENS.accent}; }
  .alc-stage.current { box-shadow: 0 0 8px rgba(245,164,0,.5); }
  .alc-connector { position: absolute; left: 100%; top: 50%; transform: translateY(-50%); width: 20px; height: 2px; background: ${TOKENS.border}; }
  .alc-stage.complete .alc-connector { background: ${TOKENS.accent}; }
  .alc-stage-label { color: ${TOKENS.secondary}; font-size: 10px; text-transform: uppercase; letter-spacing: .1em; font-weight: 700; white-space: nowrap; }
  .alc-detail { border: 1px solid rgba(245,164,0,.28); background: rgba(245,164,0,.04); border-radius: 8px; padding: 12px; display: grid; gap: 8px; }
  .alc-detail-header { color: ${TOKENS.amber}; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }
`;
```

---

## FEATURE 14: Report Generator — Section-by-Section Export and Auto-Populated F03 Attribution

### Section-by-Section PDF/Image Export

The existing `captureElementAsPng` function handles per-panel image export. For the report generator, you need a multi-section export that sequences through all selected sections, captures each, and optionally assembles a PDF:

```javascript
function SectionExportPanel({ sections, response }) {
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState({});
  const [exportFormat, setExportFormat] = useState("png");

  async function exportAll() {
    setExporting(true);
    const results = {};
    for (const section of sections) {
      setExportStatus((prev) => ({ ...prev, [section.id]: "capturing" }));
      try {
        await captureElementAsPng(section.id);
        results[section.id] = "done";
      } catch {
        results[section.id] = "error";
      }
      setExportStatus(results);
      await new Promise((r) => setTimeout(r, 120));
    }
    setExporting(false);
  }

  async function exportSingleSection(sectionId) {
    setExportStatus((prev) => ({ ...prev, [sectionId]: "capturing" }));
    try {
      await captureElementAsPng(sectionId);
      setExportStatus((prev) => ({ ...prev, [sectionId]: "done" }));
    } catch {
      setExportStatus((prev) => ({ ...prev, [sectionId]: "error" }));
    }
  }

  return (
    <div className="section-export-panel">
      <div className="sep-header">
        <div className="pro-chips">
          {["png", "json"].map((fmt) => (
            <button
              key={fmt}
              className={exportFormat === fmt ? "active" : ""}
              onClick={() => setExportFormat(fmt)}
              type="button"
            >
              {fmt.toUpperCase()}
            </button>
          ))}
        </div>
        <button
          className="run-button"
          disabled={exporting}
          onClick={exportAll}
          type="button"
        >
          {exporting ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
          Export All Sections
        </button>
      </div>

      <div className="sep-list">
        {sections.map((section) => {
          const status = exportStatus[section.id];
          return (
            <div key={section.id} className="sep-row">
              <span>{section.title}</span>
              <div className="sep-status">
                {status === "done" ? <CheckCircle2 size={14} className="positive" /> : status === "error" ? <AlertTriangle size={14} className="negative" /> : status === "capturing" ? <Loader2 size={14} className="spin" /> : null}
              </div>
              <button
                onClick={() => exportSingleSection(section.id)}
                type="button"
                className="ghost-button"
                style={{ padding: "0 10px", minHeight: "28px", fontSize: "11px" }}
              >
                <Camera size={12} /> Export
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**Auto-Populated F03 Attribution Section from Saved Workspace:**

```javascript
function AutoAttributionSection({ response, workspaceRef }) {
  // Pull attribution data from the response, or from a saved workspace
  const attributionData = response?.charts?.attribution_waterfall ?? workspaceRef?.f03_attribution;
  const exposureData = response?.charts?.exposure_bars ?? workspaceRef?.f02_exposures;
  const crowdingData = response?.charts?.crowding_composite ?? workspaceRef?.f06_crowding;

  if (!attributionData && !exposureData) {
    return (
      <div className="auto-attr-empty">
        <Info size={16} />
        <span>Connect a portfolio workspace from F02/F03 to auto-populate this section. Export your F02 workspace JSON and import it here.</span>
      </div>
    );
  }

  return (
    <div className="auto-attribution">
      {exposureData ? (
        <div className="auto-section">
          <div className="auto-section-label">Current Factor Exposures (from F02)</div>
          <StandardChart data={exposureData} type="horizontalBar" config={{ colorBySign: true }} />
        </div>
      ) : null}
      {attributionData ? (
        <div className="auto-section">
          <div className="auto-section-label">Attribution Waterfall (from F03)</div>
          <Waterfall data={attributionData} />
        </div>
      ) : null}
      {crowdingData ? (
        <div className="auto-section">
          <div className="auto-section-label">Crowding Disclosure (from F06)</div>
          <Gauge data={crowdingData} />
        </div>
      ) : null}
    </div>
  );
}
```

**External Notification/Delivery Workflow:**

Since external push notifications require a server-side integration, implement the in-app workflow as a delivery queue with local export and webhook stub:

```javascript
function NotificationDeliveryPanel({ alerts, report }) {
  const [deliveryLog, setDeliveryLog] = useState([]);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [delivering, setDelivering] = useState(false);

  async function deliverToWebhook() {
    if (!webhookUrl.trim()) { toast.error("Enter a webhook URL first."); return; }
    setDelivering(true);
    try {
      const payload = {
        type: "quant360_alert",
        timestamp: new Date().toISOString(),
        alerts: alerts.slice(0, 10),
        report_summary: report?.summary_cards?.slice(0, 3),
      };
      // Attempt delivery; in local-only mode this will likely fail CORS, so we log the intent
      try {
        await fetch(webhookUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        toast.success("Delivered to webhook");
      } catch {
        toast.error("Webhook delivery failed (CORS or network). Download the JSON payload instead.");
      }
      setDeliveryLog((prev) => [...prev, { timestamp: new Date().toISOString(), destination: webhookUrl, status: "attempted", payload_size: JSON.stringify(payload).length }]);
    } finally {
      setDelivering(false);
    }
  }

  function downloadPayload() {
    const payload = { type: "quant360_report_export", timestamp: new Date().toISOString(), alerts, report_data: report };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `quant360_report_${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast.success("Report payload downloaded");
  }

  return (
    <div className="notification-delivery">
      <div className="nd-controls">
        <input
          className="pro-input"
          placeholder="Webhook URL (https://...)"
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
        />
        <button className="run-button" disabled={delivering} onClick={deliverToWebhook} type="button">
          {delivering ? <Loader2 className="spin" size={14} /> : <Send size={14} />}
          Send to Webhook
        </button>
        <button className="ghost-button" onClick={downloadPayload} type="button">
          <Download size={14} /> Download JSON
        </button>
      </div>

      {deliveryLog.length > 0 ? (
        <div className="nd-log">
          <div className="nd-log-label">Delivery Log</div>
          {deliveryLog.map((entry, i) => (
            <div key={i} className="nd-log-row">
              <b className="mono">{entry.timestamp.slice(11, 19)}</b>
              <span>{entry.destination.slice(0, 40)}{entry.destination.length > 40 ? "..." : ""}</span>
              <em className={entry.status === "success" ? "positive" : ""}>{entry.status}</em>
              <small>{(entry.payload_size / 1024).toFixed(1)} KB</small>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
```

Add to RenderFeatureSection:

```javascript
if (section.chartType === "sectionExport") return <SectionExportPanel sections={[]} response={response} />;
if (section.chartType === "autoAttribution") return <AutoAttributionSection response={response} workspaceRef={null} />;
if (section.chartType === "notificationDelivery") return <NotificationDeliveryPanel alerts={response?.alerts || []} report={response} />;
```

CSS:

```javascript
const reportStyles = `
  .section-export-panel { display: grid; gap: 12px; }
  .sep-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .sep-list { display: grid; gap: 6px; }
  .sep-row { display: grid; grid-template-columns: 1fr 24px auto; gap: 10px; align-items: center; border: 1px solid ${TOKENS.borderSubtle}; border-radius: 6px; padding: 8px 10px; }
  .sep-row span { color: ${TOKENS.text}; font-size: 12px; }
  .sep-status { display: flex; align-items: center; }
  .auto-attribution { display: grid; gap: 14px; }
  .auto-attr-empty { display: flex; align-items: center; gap: 10px; border: 1px dashed ${TOKENS.border}; border-radius: 8px; padding: 14px; color: ${TOKENS.secondary}; font-size: 12px; }
  .auto-section { border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 12px; background: ${TOKENS.elevated}; display: grid; gap: 8px; }
  .auto-section-label { color: ${TOKENS.amber}; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }
  .notification-delivery { display: grid; gap: 12px; }
  .nd-controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .nd-log { border: 1px solid ${TOKENS.borderSubtle}; border-radius: 8px; padding: 10px; background: ${TOKENS.elevated}; display: grid; gap: 6px; }
  .nd-log-label { color: ${TOKENS.muted}; font-size: 9px; text-transform: uppercase; letter-spacing: .13em; font-weight: 800; }
  .nd-log-row { display: grid; grid-template-columns: 70px 1fr 80px 60px; gap: 10px; align-items: center; border-top: 1px solid ${TOKENS.borderSubtle}; padding-top: 5px; }
  .nd-log-row b { font-size: 10px; }
  .nd-log-row span { color: ${TOKENS.secondary}; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .nd-log-row em { font-size: 9px; font-style: normal; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: ${TOKENS.muted}; }
  .nd-log-row small { color: ${TOKENS.muted}; font-size: 10px; text-align: right; }
`;
```

---

## Consolidated recharts import addition

Your existing imports cover most chart types. Add `ComposedChart` and `Line` from recharts for F07/F10 capacity and rebalancing charts:

```javascript
// Add to your existing recharts import block:
import {
  // ... existing imports ...
  ComposedChart,
  // Line is already imported
} from "recharts";
```

---

## Consolidated styles integration

All the CSS snippets above should be concatenated into your single `styles` template literal constant at the bottom of the file. Replace:

```javascript
const styles = `
  /* ... existing styles ... */
`;
```

With:

```javascript
const styles = [
  existingStyles,
  f01Styles,
  alertFeedStyles,
  annotatedTsStyles,
  multiPortStyles,
  attrWaterfallStyles,
  freshnessStyles,
  regimeTrendStyles,
  regimeSensStyles,
  crossSectorStyles,
  multiRadarStyles,
  multiDecayStyles,
  crowdingOverlayStyles,
  oosSplitStyles,
  advCapacityStyles,
  capacityCubeStyles,
  rebalancingCostStyles,
  stressStyles,
  dnaStyles,
  signalMonitorStyles,
  reportStyles,
  crisisPresetStyles,
  rollingHeatmapStyles,
].join("\n");
```
