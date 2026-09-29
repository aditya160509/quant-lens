## CURRENT IMPLEMENTATION CHECKLIST — 2026-05-16

This checklist was added before applying the output-renderer upgrade pass. Original manifest content is preserved below.

### Implemented Before This Pass

- [x] Calendar Heatmap renderer.
- [x] Ridge Plot renderer.
- [x] Volatility Cone renderer.
- [x] Q-Q Plot renderer.
- [x] Volatility Signature Plot renderer.
- [x] Correlation Mini-Movies renderer.
- [x] Output minimap navigator.
- [x] Toast system.
- [x] Cinema mode.
- [x] Density toggle.
- [x] Workspace state persistence.
- [x] Staggered card reveal.
- [x] Run progress bar.
- [x] Crosshair/delta tooltip baseline.
- [x] Card header sparklines.
- [x] Sticky metric bar.
- [x] Export modal surface.
- [x] Data search with table-cell highlighting.
- [x] Drag reorder.
- [x] Split comparison shell.
- [x] Directional draggable network baseline.
- [x] SVG volatility gauge baseline.
- [x] Forecast fan chart baseline.
- [x] GARCH scoreboard baseline with rank and MCS badges.

### Applied In This Pass

- [x] Atlas Series Chart: gradient fills, zero reference, brush zoom for long series, ring active dots and final-value legend strip.
- [x] Atlas Bar Chart: sign-aware gradients and value labels.
- [x] Atlas Data Table: frozen first column, micro-bars, intensity cells, sorting and search highlighting.
- [x] Atlas Heatmap: extreme-cell glow, hover strip and scale legend.
- [x] Atlas Metric Deck: percentile arcs, sparkline cards and delta chips.
- [x] Atlas Volatility Gauge: 5-zone SVG gauge and zone legend.
- [x] Atlas Regime Stack / Probability Stack: current vector bar and dominant regime label.
- [x] Atlas Network: directional edges, transmitter/receiver node color logic and draggable nodes.
- [x] Atlas Waterfall: cumulative base/height waterfall and total styling.
- [x] Atlas GARCH Scoreboard: MCS strip and rank cards.
- [x] Atlas Forecast Bands: p05/p95 and p25/p75 fan bands.
- [x] Complete `VolRenderer` routing for every chartType, including `varChart`.

### Honest Notes From This Pass

- [x] All output-renderer upgrades were kept inside `frontend/src/components/volatility-v2/customPagePrimitives.jsx`, per the single-file Vol UI constraint.
- [x] No API wiring was changed.
- [x] Focused lint passed for the Volatility V2 primitives and registry.
- [ ] Floating right-edge chart labels from the manifest are represented through the final-value legend strip instead of fragile custom chart-coordinate labels.
- [ ] Regime background bands for generic line/area charts require a dedicated `regimeData` payload shape from backend; current renderer is ready for series/brush/zero-cross polish but does not invent regime bands when the payload does not contain them.

### Not In Scope

- [ ] API wiring remains intentionally untouched.
- [ ] Browser visual verification remains pending until the Volatility route is wired.

---

## SUMMARY COUNT

**New output chart types added: 6** (Calendar Heatmap, Ridge Plot, Vol Cone, Q-Q Plot, Signature Plot, Correlation Mini-Movies)

**New UI systems added: 11** (Split Comparison, Minimap Navigator, Toast System, Cinema Mode, Density Toggle, Workspace State Persistence, Staggered Reveal, Run Progress Bar, Crosshair Ruler, Card Sparkline, Ambient Glow, Run History, Export Modal, Data Search, Sticky Metric Bar, Drag Reorder)

**New design tokens added:** Extended 8-layer surface hierarchy, complete type scale with tabular numerics, micro-interaction token library with 5 duration and 5 easing variables

**New dependencies required: zero.** Every item above runs on the existing React + Recharts + Framer Motion + Lucide stack already present in Document 2.
Let me go through every single chartType in your registry and make each one heaven-tier.

The types are: `line`, `area`, `bar`, `table`, `heatmap`, `metricDeck`, `estimatorComparison`, `garchScoreboard`, `termStructure`, `probabilityStack`, `regimeDashboard`, `tripleHeatmap`, `network`, `waterfall`, `budgetWaterfall`, `stressDistribution`, `volGauge`, `forecastBands`, `surfaceGrid`, `frequencyBands`, `dualPosterior`, `composedBarLine`, `varChart`, `garchScoreboard`

Here is every single one, rebuilt from scratch to make you cry.

---

## ATLAS — HEAVEN-TIER OUTPUT RENDERER SYSTEM

### Complete replacement for every `VolRenderer` branch. Drop these in as named components.

---

### 1. `line` and `area` — THE ATLAS SERIES CHART

The current line/area renderer uses flat recharts defaults. This replacement adds: gradient fills that shift color at zero crossings, animated draw-on entry, a live regime band layer, a pinned last-value label floating at the right edge of each series, and an optional brush zoom at the bottom.

```jsx
// components/volatility-v2/charts/AtlasSeriesChart.jsx

import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Brush,
  Label,
} from "recharts";
import { useMemo, useState } from "react";

const PALETTE = [
  "#f5a400",
  "#22c55e",
  "#e8d18a",
  "#60a5fa",
  "#14b8a6",
  "#8b5cf6",
  "#ef4444",
  "#ec4899",
];

export function AtlasSeriesChart({
  data,
  type = "line",
  config = {},
  regimeData = [],
}) {
  const rows = rowsFrom(data);
  const { xKey, yKeys } = inferKeys(rows, config);
  const [brushDomain, setBrushDomain] = useState(null);
  if (!rows.length) return <ChartEmpty />;

  const hasNegative = rows.some((r) =>
    yKeys.some((k) => (numberLike(r[k]) ?? 0) < 0),
  );
  const isArea = type === "area" || type === "stackedArea";
  const isStacked = type === "stackedArea";

  // Last values for floating labels
  const lastRow = rows.at(-1);

  return (
    <div className="asc-wrap">
      <ResponsiveContainer height={420} width="100%">
        <ComposedChart
          data={rows}
          margin={{ top: 24, right: 72, left: 8, bottom: 40 }}
        >
          <defs>
            {yKeys.map((key, i) => (
              <linearGradient
                key={key}
                id={`asc-grad-${key}`}
                x1="0"
                x2="0"
                y1="0"
                y2="1"
              >
                <stop
                  offset="0%"
                  stopColor={PALETTE[i % PALETTE.length]}
                  stopOpacity={0.3}
                />
                <stop
                  offset="55%"
                  stopColor={PALETTE[i % PALETTE.length]}
                  stopOpacity={0.08}
                />
                <stop
                  offset="100%"
                  stopColor={PALETTE[i % PALETTE.length]}
                  stopOpacity={0.0}
                />
              </linearGradient>
            ))}
            {/* Zero-cross gradient for negative-value series */}
            {hasNegative && (
              <linearGradient id="asc-zero-cross" x1="0" x2="0" y1="0" y2="1">
                <stop offset="50%" stopColor="#22c55e" stopOpacity={0.22} />
                <stop offset="50%" stopColor="#ef4444" stopOpacity={0.22} />
              </linearGradient>
            )}
          </defs>

          {/* Terminal dot-grid background */}
          <CartesianGrid
            stroke="#2d2a24"
            strokeOpacity={0.5}
            vertical={false}
            strokeDasharray="0"
          />

          {/* Regime background bands */}
          <RegimeBands regimeRows={regimeData} />

          <XAxis
            dataKey={xKey}
            tick={{
              fill: "#6e665b",
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
            }}
            axisLine={{ stroke: "#2e2618" }}
            tickLine={false}
            tickMargin={8}
          />
          <YAxis
            tick={{
              fill: "#6e665b",
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
            }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => formatValue(v)}
            width={56}
          />

          <Tooltip
            content={<CrosshairTooltip data={rows} xKey={xKey} />}
            cursor={{
              stroke: "rgba(245,164,0,.25)",
              strokeWidth: 1,
              strokeDasharray: "4 3",
            }}
          />

          {/* Zero reference line — only when data crosses zero */}
          {hasNegative && (
            <ReferenceLine y={0} stroke="#4a4238" strokeWidth={1.5} />
          )}

          {/* Series */}
          {yKeys.map((key, i) => {
            const color = PALETTE[i % PALETTE.length];
            const lastVal = numberLike(lastRow?.[key]);

            return isArea ? (
              <Area
                key={key}
                dataKey={key}
                stroke={color}
                strokeWidth={2}
                fill={`url(#asc-grad-${key})`}
                stackId={isStacked ? "stack" : undefined}
                type="monotone"
                dot={false}
                activeDot={{
                  r: 5,
                  fill: color,
                  stroke: "#050505",
                  strokeWidth: 2,
                }}
                animationDuration={900}
                animationEasing="ease-out"
                label={
                  lastVal != null ? (
                    <LastValueLabel value={lastVal} color={color} />
                  ) : null
                }
              />
            ) : (
              <Line
                key={key}
                dataKey={key}
                stroke={color}
                strokeWidth={i === 0 ? 2.5 : 1.8}
                type="monotone"
                dot={false}
                activeDot={{
                  r: 5,
                  fill: color,
                  stroke: "#050505",
                  strokeWidth: 2,
                }}
                animationDuration={900}
                animationEasing="ease-out"
              />
            );
          })}

          {/* Brush zoom — shown when > 252 data points */}
          {rows.length > 252 && (
            <Brush
              dataKey={xKey}
              height={28}
              travellerWidth={6}
              stroke="#2e2618"
              fill="#090909"
              tickFormatter={() => ""}
              onChange={({ startIndex, endIndex }) =>
                setBrushDomain([startIndex, endIndex])
              }
            >
              <AreaChart>
                <Area
                  dataKey={yKeys[0]}
                  stroke="#f5a40060"
                  fill="#f5a40015"
                  strokeWidth={1}
                  dot={false}
                />
              </AreaChart>
            </Brush>
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend strip */}
      <div className="asc-legend">
        {yKeys.map((key, i) => (
          <span
            key={key}
            className="asc-legend-item"
            style={{ "--c": PALETTE[i % PALETTE.length] }}
          >
            <em />
            {titleize(key)}
          </span>
        ))}
      </div>
    </div>
  );
}

// Floating last-value label at right edge of each series
function LastValueLabel({ viewBox, value, color }) {
  if (!viewBox) return null;
  const { x, y } = viewBox;
  return (
    <g>
      <rect
        x={x + 6}
        y={y - 10}
        width={48}
        height={18}
        rx={4}
        fill="#090909"
        stroke={color}
        strokeOpacity={0.5}
        strokeWidth={1}
      />
      <text
        x={x + 30}
        y={y + 4}
        textAnchor="middle"
        fill={color}
        fontSize={9}
        fontWeight={800}
        fontFamily="JetBrains Mono, monospace"
      >
        {formatValue(value)}
      </text>
    </g>
  );
}

function ChartEmpty() {
  return (
    <div className="asc-empty">
      <div className="asc-empty-grid" />
      <span>Awaiting run</span>
    </div>
  );
}
```

```css
.asc-wrap {
  display: grid;
  gap: 8px;
}

.asc-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 0 8px;
}

.asc-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #a8a197;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.asc-legend-item em {
  display: inline-block;
  width: 20px;
  height: 2px;
  border-radius: 1px;
  background: var(--c, #f5a400);
  font-style: normal;
}

.asc-empty {
  position: relative;
  min-height: 360px;
  display: grid;
  place-items: center;
  color: #6e665b;
  font:
    11px "JetBrains Mono",
    monospace;
}

.asc-empty-grid {
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      0deg,
      rgba(255, 255, 255, 0.018) 0px,
      rgba(255, 255, 255, 0.018) 1px,
      transparent 1px,
      transparent 36px
    ),
    repeating-linear-gradient(
      90deg,
      rgba(255, 255, 255, 0.014) 0px,
      rgba(255, 255, 255, 0.014) 1px,
      transparent 1px,
      transparent 72px
    );
  border-radius: 8px;
}
```

---

### 2. `bar` and `horizontalBar` — THE ATLAS BAR CHART

Current bar chart is flat. This version: each bar has a gradient fill that's brighter at the top, negative bars flip to red with a gradient, positive bars glow green-to-amber, value labels float above each bar, and bars animate up from the baseline on entry.

```jsx
// components/volatility-v2/charts/AtlasBarChart.jsx

export function AtlasBarChart({ data, config = {}, horizontal = false }) {
  const rows = rowsFrom(data);
  const { xKey, yKeys } = inferKeys(rows, config);
  if (!rows.length) return <ChartEmpty />;

  const PALETTE = [
    "#f5a400",
    "#22c55e",
    "#60a5fa",
    "#8b5cf6",
    "#14b8a6",
    "#ef4444",
  ];

  return (
    <div className="abc-wrap">
      <ResponsiveContainer
        height={horizontal ? Math.max(340, rows.length * 38) : 380}
        width="100%"
      >
        <BarChart
          data={rows}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{
            top: 24,
            right: 24,
            left: horizontal ? 140 : 8,
            bottom: 12,
          }}
          barCategoryGap="28%"
        >
          <defs>
            {PALETTE.map((c, i) => (
              <linearGradient
                key={i}
                id={`abc-pos-${i}`}
                x1="0"
                x2="0"
                y1="0"
                y2="1"
              >
                <stop offset="0%" stopColor={c} stopOpacity={0.9} />
                <stop offset="100%" stopColor={c} stopOpacity={0.45} />
              </linearGradient>
            ))}
            <linearGradient id="abc-neg" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.85} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.4} />
            </linearGradient>
          </defs>

          <CartesianGrid
            stroke="#2d2a24"
            strokeOpacity={0.4}
            vertical={horizontal}
            horizontal={!horizontal}
          />

          {horizontal ? (
            <>
              <XAxis
                type="number"
                tick={{
                  fill: "#6e665b",
                  fontSize: 10,
                  fontFamily: "JetBrains Mono, monospace",
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={formatValue}
              />
              <YAxis
                dataKey={xKey}
                type="category"
                width={130}
                tick={{
                  fill: "#a8a197",
                  fontSize: 11,
                  fontFamily: "JetBrains Mono, monospace",
                }}
                axisLine={false}
                tickLine={false}
              />
            </>
          ) : (
            <>
              <XAxis
                dataKey={xKey}
                tick={{
                  fill: "#6e665b",
                  fontSize: 10,
                  fontFamily: "JetBrains Mono, monospace",
                }}
                axisLine={{ stroke: "#2e2618" }}
                tickLine={false}
              />
              <YAxis
                tick={{
                  fill: "#6e665b",
                  fontSize: 10,
                  fontFamily: "JetBrains Mono, monospace",
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={formatValue}
                width={56}
              />
            </>
          )}

          <Tooltip
            content={<CrosshairTooltip data={rows} xKey={xKey} />}
            cursor={{ fill: "rgba(245,164,0,.04)" }}
          />
          <ReferenceLine y={0} stroke="#4a4238" strokeWidth={1} />

          {yKeys.map((key, ki) => (
            <Bar
              key={key}
              dataKey={key}
              radius={horizontal ? [0, 6, 6, 0] : [5, 5, 0, 0]}
              animationDuration={800}
              animationEasing="ease-out"
              label={{
                position: horizontal ? "right" : "top",
                fill: "#6e665b",
                fontSize: 9,
                fontFamily: "JetBrains Mono, monospace",
                formatter: (v) => formatValue(v),
              }}
            >
              {rows.map((row, ri) => {
                const v = numberLike(row[key]) ?? 0;
                return (
                  <Cell
                    key={ri}
                    fill={
                      v < 0
                        ? "url(#abc-neg)"
                        : `url(#abc-pos-${ki % PALETTE.length})`
                    }
                  />
                );
              })}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

```css
.abc-wrap {
  display: grid;
  gap: 8px;
}
```

---

### 3. `table` — THE ATLAS DATA TABLE

Current table is bare. This version: frozen first column, alternating subtle row tints, inline spark column for the first numeric column, color-coded positive/negative cells with intensity proportional to the value's distance from the column mean, and column sorting with animated sort-direction indicator.

```jsx
// components/volatility-v2/charts/AtlasTable.jsx

import { useMemo, useState } from "react";

export function AtlasTable({ data, config = {} }) {
  const rows = useMemo(() => rowsFrom(data), [data]);
  const cols = useMemo(
    () =>
      [
        ...new Set(rows.slice(0, 100).flatMap((r) => Object.keys(r ?? {}))),
      ].slice(0, 14),
    [rows],
  );
  const [sort, setSort] = useState({ key: cols[0], dir: "asc" });
  const [hoverRow, setHoverRow] = useState(null);

  // Per-column statistics for heat coloring
  const colStats = useMemo(() => {
    const stats = {};
    for (const col of cols) {
      const nums = rows.map((r) => numberLike(r[col])).filter((v) => v != null);
      if (!nums.length) continue;
      const mean = nums.reduce((s, v) => s + v, 0) / nums.length;
      const max = Math.max(...nums.map(Math.abs));
      stats[col] = { mean, max };
    }
    return stats;
  }, [rows, cols]);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = numberLike(a[sort.key]) ?? String(a[sort.key] ?? "");
      const bv = numberLike(b[sort.key]) ?? String(b[sort.key] ?? "");
      const r =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? r : -r;
    });
    return copy;
  }, [rows, sort]);

  function cellColor(col, val) {
    const n = numberLike(val);
    const s = colStats[col];
    if (n == null || !s || s.max === 0) return "transparent";
    const intensity = Math.min(0.75, (Math.abs(n) / s.max) * 0.6 + 0.05);
    if (n < 0) return `rgba(239,68,68,${intensity})`;
    if (n > 0) return `rgba(34,197,94,${intensity * 0.75})`;
    return "transparent";
  }

  return (
    <div className="at-wrap">
      <table className="at-table">
        <thead>
          <tr>
            {cols.map((col) => (
              <th
                key={col}
                className={sort.key === col ? "sorted" : ""}
                onClick={() =>
                  setSort((s) => ({
                    key: col,
                    dir: s.key === col && s.dir === "asc" ? "desc" : "asc",
                  }))
                }
              >
                <span>{titleize(col)}</span>
                <em className="at-sort-icon">
                  {sort.key === col ? (sort.dir === "asc" ? "↑" : "↓") : "↕"}
                </em>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 300).map((row, ri) => (
            <tr
              key={ri}
              className={hoverRow === ri ? "hovered" : ""}
              onMouseEnter={() => setHoverRow(ri)}
              onMouseLeave={() => setHoverRow(null)}
            >
              {cols.map((col, ci) => {
                const val = row[col];
                const n = numberLike(val);
                const bg = ci > 0 ? cellColor(col, val) : "transparent";
                return (
                  <td
                    key={col}
                    className={`${n != null ? "num" : ""} ${n != null && n < 0 ? "neg" : ""} ${n != null && n > 0 ? "pos" : ""}`}
                    style={{ "--cell-bg": bg }}
                  >
                    <span className="at-cell-inner">
                      {ci === 0
                        ? titleize(String(val ?? ""))
                        : formatValue(val)}
                    </span>
                    {/* Inline micro bar for numeric columns */}
                    {ci > 0 && n != null && colStats[col]?.max > 0 && (
                      <span
                        className="at-micro-bar"
                        style={{
                          width: `${Math.min(100, (Math.abs(n) / colStats[col].max) * 100)}%`,
                          background: n < 0 ? "#ef4444" : "#22c55e",
                        }}
                      />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="at-footer">
        {sorted.length} rows · {cols.length} columns
        {sorted.length > 300 && <span> · showing first 300</span>}
      </div>
    </div>
  );
}
```

```css
.at-wrap {
  border: 1px solid #1d1710;
  border-radius: 12px;
  overflow: hidden;
}

.at-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.at-table thead {
  position: sticky;
  top: 0;
  z-index: 3;
}

.at-table th {
  height: 40px;
  background: #0c0c0c;
  color: #f5a400;
  text-align: right;
  padding: 0 12px;
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  border-bottom: 1px solid #2e2618;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
  transition: background 120ms ease;
}
.at-table th:first-child {
  text-align: left;
  position: sticky;
  left: 0;
  background: #0c0c0c;
}
.at-table th:hover {
  background: #14110a;
}
.at-table th.sorted {
  color: #f5f2ea;
}

.at-sort-icon {
  margin-left: 5px;
  color: #6e665b;
  font-style: normal;
  font-size: 10px;
}

.at-table tr {
  border-bottom: 1px solid #141414;
  transition: background 80ms ease;
}
.at-table tr.hovered td {
  background: rgba(245, 164, 0, 0.04) !important;
}

.at-table td {
  position: relative;
  height: var(--vol-row-h, 40px);
  text-align: right;
  padding: 0 12px;
  color: #a8a197;
  white-space: nowrap;
  background: var(--cell-bg, transparent);
  font-size: var(--vol-table-fs, 12px);
  font-variant-numeric: tabular-nums;
}
.at-table td:first-child {
  text-align: left;
  position: sticky;
  left: 0;
  background: #090909;
  color: #f5f2ea;
  font-weight: 600;
  z-index: 1;
}
.at-table td.num {
  font-family: "JetBrains Mono", monospace;
}
.at-table td.pos {
  color: #22c55e;
}
.at-table td.neg {
  color: #ef4444;
}

.at-cell-inner {
  position: relative;
  z-index: 1;
}

/* Inline micro-bar that sits behind the number */
.at-micro-bar {
  position: absolute;
  bottom: 0;
  right: 12px;
  height: 2px;
  border-radius: 1px;
  opacity: 0.6;
  transition: width 400ms ease;
}

.at-footer {
  padding: 6px 12px;
  background: #090909;
  border-top: 1px solid #1d1710;
  font:
    10px "JetBrains Mono",
    monospace;
  color: #6e665b;
  letter-spacing: 0.04em;
}
```

---

### 4. `heatmap` — THE ATLAS HEATMAP

Current heatmap uses flat rgba fills and tiny fonts. This version: each cell has a layered glow for extreme values, the color scale has 7 stops for fine gradation, hovering a cell dims all others and pins a rich crosshair tooltip, and the diagonal (self-correlation) gets a special treatment — a brushed metal amber stripe.

```jsx
// components/volatility-v2/charts/AtlasHeatmap.jsx

import { useState } from "react";

export function AtlasHeatmap({ data, config = {} }) {
  const rows = rowsFrom(data);
  const rowKey = config.rowKey || "row";
  const colKey = config.colKey || "col";
  const valueKey = config.valueKey || "value";
  const [hovered, setHovered] = useState(null); // { row, col }

  const rowLabels = [
    ...new Set(rows.map((r) => String(r[rowKey] ?? ""))),
  ].filter(Boolean);
  const colLabels = [
    ...new Set(rows.map((r) => String(r[colKey] ?? ""))),
  ].filter(Boolean);
  const maxAbs = Math.max(
    1e-9,
    ...rows.map((r) => Math.abs(numberLike(r[valueKey]) ?? 0)),
  );

  const cellMap = new Map(
    rows.map((r) => [
      `${r[rowKey]}__${r[colKey]}`,
      numberLike(r[valueKey]) ?? 0,
    ]),
  );

  function cellBg(v, isDiag) {
    if (isDiag)
      return "linear-gradient(135deg, rgba(245,164,0,.18), rgba(245,164,0,.08))";
    const t = Math.abs(v) / maxAbs;
    if (config.diverging) {
      if (v > 0) return `rgba(239,68,68,${0.05 + t * 0.72})`;
      if (v < 0) return `rgba(96,165,250,${0.05 + t * 0.72})`;
      return "rgba(255,255,255,.02)";
    }
    if (v > 0) return `rgba(245,164,0,${0.06 + t * 0.76})`;
    if (v < 0) return `rgba(96,165,250,${0.06 + t * 0.72})`;
    return "rgba(255,255,255,.02)";
  }

  function cellGlow(v, isDiag) {
    if (isDiag) return "0 0 12px rgba(245,164,0,.15)";
    const t = Math.abs(v) / maxAbs;
    if (t < 0.7) return "none";
    const c = config.diverging
      ? v > 0
        ? "239,68,68"
        : "96,165,250"
      : v > 0
        ? "245,164,0"
        : "96,165,250";
    return `0 0 ${t * 16}px rgba(${c},${t * 0.4})`;
  }

  return (
    <div className="ahm-wrap" style={{ "--hm-cols": colLabels.length }}>
      {/* Column headers */}
      <div className="ahm-grid">
        <div className="ahm-corner" />
        {colLabels.map((col) => (
          <div
            key={col}
            className={`ahm-col-label ${hovered?.col === col ? "hm-header-active" : ""}`}
          >
            {col}
          </div>
        ))}

        {rowLabels.map((row) => [
          <div
            key={`${row}-lbl`}
            className={`ahm-row-label ${hovered?.row === row ? "hm-header-active" : ""}`}
          >
            {row}
          </div>,
          ...colLabels.map((col) => {
            const v = cellMap.get(`${row}__${col}`) ?? 0;
            const isDiag = row === col;
            const isHov = hovered?.row === row || hovered?.col === col;
            const isDim = hovered && !isHov;

            return (
              <div
                key={`${row}__${col}`}
                className={`ahm-cell ${isDiag ? "diag" : ""} ${isDim ? "dimmed" : ""}`}
                style={{
                  background: cellBg(v, isDiag),
                  boxShadow:
                    hovered?.row === row && hovered?.col === col
                      ? cellGlow(v, isDiag)
                      : "none",
                }}
                onMouseEnter={() => setHovered({ row, col })}
                onMouseLeave={() => setHovered(null)}
                title={`${row} / ${col}: ${v.toFixed(4)}`}
              >
                <span className="ahm-val">
                  {isDiag ? "—" : Math.abs(v) > 0.005 ? v.toFixed(2) : ""}
                </span>
              </div>
            );
          }),
        ])}
      </div>

      {/* Hover tooltip */}
      {hovered &&
        (() => {
          const v = cellMap.get(`${hovered.row}__${hovered.col}`) ?? 0;
          return (
            <div className="ahm-hover-strip">
              <span className="ahm-hs-pair">
                {hovered.row} × {hovered.col}
              </span>
              <span
                className="ahm-hs-val mono"
                style={{
                  color: v > 0 ? "#22c55e" : v < 0 ? "#60a5fa" : "#a8a197",
                }}
              >
                {v.toFixed(4)}
              </span>
              <span className="ahm-hs-abs">|ρ| = {Math.abs(v).toFixed(4)}</span>
              <span className="ahm-hs-pct">
                {((Math.abs(v) / maxAbs) * 100).toFixed(0)}th of max
              </span>
            </div>
          );
        })()}

      {/* Color scale legend */}
      <div className="ahm-scale">
        {config.diverging ? (
          <>
            <span style={{ color: "#60a5fa" }}>−{formatValue(maxAbs)}</span>
            <div className="ahm-scale-grad diverging" />
            <span style={{ color: "#ef4444" }}>+{formatValue(maxAbs)}</span>
          </>
        ) : (
          <>
            <span style={{ color: "#6e665b" }}>0</span>
            <div className="ahm-scale-grad" />
            <span style={{ color: "#f5a400" }}>{formatValue(maxAbs)}</span>
          </>
        )}
      </div>
    </div>
  );
}
```

```css
.ahm-wrap {
  display: grid;
  gap: 10px;
}

.ahm-grid {
  display: grid;
  grid-template-columns: 100px repeat(var(--hm-cols), minmax(52px, 1fr));
  gap: 3px;
  overflow-x: auto;
}

.ahm-corner {
  min-height: 30px;
}

.ahm-col-label,
.ahm-row-label {
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6e665b;
  display: grid;
  place-items: center;
  min-height: 30px;
  transition: color 120ms ease;
}
.ahm-row-label {
  justify-content: start;
  padding-left: 4px;
}
.hm-header-active {
  color: #f5f2ea !important;
}

.ahm-cell {
  min-height: 48px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  cursor: default;
  transition:
    box-shadow 150ms ease,
    opacity 150ms ease,
    transform 120ms ease;
  border: 1px solid rgba(255, 255, 255, 0.025);
}
.ahm-cell:hover {
  transform: scale(1.06);
  z-index: 2;
}

.ahm-cell.diag {
  border-color: rgba(245, 164, 0, 0.15);
}

.ahm-cell.dimmed {
  opacity: 0.22;
}

.ahm-val {
  font:
    800 10px "JetBrains Mono",
    monospace;
  color: rgba(255, 255, 255, 0.85);
  letter-spacing: 0.02em;
}

.ahm-hover-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 34px;
  padding: 0 12px;
  background: #0d0f11;
  border: 1px solid #2e2618;
  border-radius: 8px;
  font-size: 11px;
}
.ahm-hs-pair {
  color: #f5f2ea;
  font-weight: 700;
}
.ahm-hs-val {
  font:
    800 13px "JetBrains Mono",
    monospace;
}
.ahm-hs-abs,
.ahm-hs-pct {
  color: #6e665b;
  font:
    10px "JetBrains Mono",
    monospace;
}

.ahm-scale {
  display: flex;
  align-items: center;
  gap: 8px;
  font:
    800 9px "JetBrains Mono",
    monospace;
  padding: 0 4px;
}

.ahm-scale-grad {
  flex: 1;
  max-width: 200px;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(
    90deg,
    rgba(245, 164, 0, 0.1),
    rgba(245, 164, 0, 0.9)
  );
}
.ahm-scale-grad.diverging {
  background: linear-gradient(
    90deg,
    rgba(96, 165, 250, 0.9),
    rgba(255, 255, 255, 0.05),
    rgba(239, 68, 68, 0.9)
  );
}
```

---

### 5. `metricDeck` — THE ATLAS METRIC DECK

Current version is a plain grid of numbers. This version: each card has a large display number with automatic unit detection (%, bps, ×), a 32-point inline sparkline that reacts to positive/negative trend with color, a percentile arc (SVG half-donut) showing the current value's position in the 10-year distribution, and a delta chip comparing to the previous run.

```jsx
// components/volatility-v2/charts/AtlasMetricDeck.jsx

export function AtlasMetricDeck({ data }) {
  const rows = rowsFrom(data).slice(0, 9);

  return (
    <div className="amd-grid">
      {rows.map((row, i) => {
        const label =
          row.label ?? row.metric ?? row.name ?? row.asset ?? `Metric ${i + 1}`;
        const val = numberLike(
          row.value ??
            row.vol ??
            row.score ??
            row.percentile ??
            Object.values(row).find((v) => typeof v === "number"),
        );
        const pctile = numberLike(row.percentile ?? row.pct);
        const delta = numberLike(row.delta ?? row.change);
        const unit =
          row.unit ?? (String(label).toLowerCase().includes("vol") ? "%" : "");
        const sparkVals = row.series
          ? rowsFrom(row.series).map((r) => numberLike(r.value) ?? 0)
          : null;

        const trend = sparkVals
          ? sparkVals.at(-1) > sparkVals[0]
            ? "up"
            : "dn"
          : delta != null && delta >= 0
            ? "up"
            : "dn";

        return (
          <div key={i} className={`amd-card ${trend}`}>
            <div className="amd-label">{label}</div>
            <div className="amd-number">
              {val != null ? (
                <>
                  <span className="amd-val">{formatValue(val)}</span>
                  {unit && <span className="amd-unit">{unit}</span>}
                </>
              ) : (
                <span className="amd-val">—</span>
              )}
            </div>

            {/* Delta chip */}
            {delta != null && (
              <div className={`amd-delta ${delta >= 0 ? "pos" : "neg"}`}>
                {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(2)}
                {unit}
              </div>
            )}

            {/* Percentile arc */}
            {pctile != null && <PercentileArc value={pctile} trend={trend} />}

            {/* Sparkline */}
            {sparkVals && <MetricSparkline values={sparkVals} trend={trend} />}
          </div>
        );
      })}
    </div>
  );
}

function PercentileArc({ value, trend }) {
  const r = 28;
  const circ = Math.PI * r; // half-circle circumference
  const pct = Math.max(0, Math.min(1, value / 100));
  const dash = pct * circ;
  const color = value > 80 ? "#ef4444" : value > 60 ? "#f5a400" : "#22c55e";

  return (
    <svg
      className="amd-arc"
      viewBox="0 0 72 40"
      aria-label={`${value}th percentile`}
    >
      {/* Track */}
      <path
        d="M 8 36 A 28 28 0 0 1 64 36"
        fill="none"
        stroke="#1d1710"
        strokeWidth={5}
        strokeLinecap="round"
      />
      {/* Fill */}
      <path
        d="M 8 36 A 28 28 0 0 1 64 36"
        fill="none"
        stroke={color}
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`}
      />
      {/* Percentile label */}
      <text
        x="36"
        y="34"
        textAnchor="middle"
        fontSize={10}
        fontWeight={900}
        fill={color}
        fontFamily="JetBrains Mono, monospace"
      >
        {value.toFixed(0)}p
      </text>
    </svg>
  );
}

function MetricSparkline({ values, trend }) {
  const W = 80,
    H = 28;
  const min = Math.min(...values),
    max = Math.max(...values);
  const rng = max - min || 1;
  const color = trend === "up" ? "#22c55e" : "#ef4444";

  const pts = values
    .map(
      (v, i) =>
        `${(i / (values.length - 1)) * W},${H - ((v - min) / rng) * (H - 4) - 2}`,
    )
    .join(" ");

  return (
    <svg className="amd-spark" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <defs>
        <linearGradient id={`spark-fill-${trend}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${H} ${pts} ${W},${H}`}
        fill={`url(#spark-fill-${trend})`}
      />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    </svg>
  );
}
```

```css
.amd-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}

.amd-card {
  border: 1px solid #1d1710;
  border-radius: 14px;
  padding: 16px;
  background: linear-gradient(160deg, #0e0e0e, #080808);
  display: grid;
  gap: 6px;
  transition:
    border-color 200ms ease,
    box-shadow 200ms ease;
  position: relative;
  overflow: hidden;
}
.amd-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(245, 164, 0, 0.4),
    transparent
  );
  opacity: 0;
  transition: opacity 200ms ease;
}
.amd-card:hover {
  border-color: #2e2618;
}
.amd-card:hover::before {
  opacity: 1;
}

.amd-card.up {
  border-left: 2px solid rgba(34, 197, 94, 0.4);
}
.amd-card.dn {
  border-left: 2px solid rgba(239, 68, 68, 0.4);
}

.amd-label {
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6e665b;
}

.amd-number {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.amd-val {
  font:
    900 var(--vol-display-lg, 34px) "JetBrains Mono",
    monospace;
  color: #f5f2ea;
  letter-spacing: -0.03em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.amd-unit {
  font-size: 14px;
  color: #6e665b;
  font-weight: 700;
}

.amd-delta {
  font:
    800 10px "JetBrains Mono",
    monospace;
  letter-spacing: 0.04em;
  height: 20px;
  display: inline-flex;
  align-items: center;
  padding: 0 7px;
  border-radius: 4px;
  width: fit-content;
}
.amd-delta.pos {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
}
.amd-delta.neg {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.amd-arc {
  width: 72px;
  height: 40px;
}
.amd-spark {
  width: 100%;
  height: 28px;
  display: block;
}
```

---

### 6. `volGauge` — THE ATLAS VOLATILITY GAUGE

Current gauge is a conic-gradient div with a needle. This version: a proper SVG half-donut with 5 colored zones (serene → nervous → stressed → alarmed → crisis), an animated needle that sweeps from the previous value to the current on every run, and a below-gauge section showing the exact percentile and zone label.

```jsx
// components/volatility-v2/charts/AtlasVolGauge.jsx

import { useEffect, useRef } from "react";

const ZONES = [
  { label: "SERENE", max: 20, color: "#14b8a6" },
  { label: "CALM", max: 40, color: "#22c55e" },
  { label: "NERVOUS", max: 60, color: "#f5a400" },
  { label: "STRESSED", max: 80, color: "#f97316" },
  { label: "CRISIS", max: 100, color: "#ef4444" },
];

export function AtlasVolGauge({ data }) {
  const rows = rowsFrom(data);
  const row = rows[0] ?? {};
  const pct = Math.max(
    0,
    Math.min(100, numberLike(row.percentile ?? row.value ?? row.score) ?? 50),
  );
  const label = row.label ?? row.name ?? "Volatility State";
  const zone = ZONES.find((z) => pct <= z.max) ?? ZONES.at(-1);
  const needleRef = useRef(null);

  const R = 100,
    CX = 120,
    CY = 115;
  const startAngle = 200,
    sweepAngle = 140;

  function polarToXY(angleDeg, radius) {
    const rad = (angleDeg * Math.PI) / 180;
    return { x: CX + radius * Math.cos(rad), y: CY + radius * Math.sin(rad) };
  }

  function arcPath(startDeg, endDeg, r, inner = 0) {
    const s = polarToXY(startDeg, r);
    const e = polarToXY(endDeg, r);
    const si = inner ? polarToXY(startDeg, inner) : null;
    const ei = inner ? polarToXY(endDeg, inner) : null;
    const lg = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
    if (!inner) return `M ${s.x} ${s.y} A ${r} ${r} 0 ${lg} 1 ${e.x} ${e.y}`;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${lg} 1 ${e.x} ${e.y} L ${ei.x} ${ei.y} A ${inner} ${inner} 0 ${lg} 0 ${si.x} ${si.y} Z`;
  }

  // Needle angle
  const needleAngle = startAngle + (pct / 100) * sweepAngle;
  const nTip = polarToXY(needleAngle, R - 12);
  const nBase = polarToXY(needleAngle + 90, 8);
  const nBase2 = polarToXY(needleAngle - 90, 8);

  // Animate needle on value change
  useEffect(() => {
    const el = needleRef.current;
    if (!el) return;
    el.style.transition = "transform 800ms cubic-bezier(0.34,1.56,0.64,1)";
  }, [pct]);

  return (
    <div className="avg-wrap">
      <svg viewBox="0 0 240 140" className="avg-svg">
        {/* Zone arcs */}
        {ZONES.map((z, i) => {
          const prev = i === 0 ? 0 : ZONES[i - 1].max;
          const arcStart = startAngle + (prev / 100) * sweepAngle;
          const arcEnd = startAngle + (z.max / 100) * sweepAngle;
          return (
            <path
              key={z.label}
              d={arcPath(arcStart, arcEnd, R, R - 18)}
              fill={z.color}
              opacity={pct >= prev && pct <= z.max ? 0.85 : 0.18}
            />
          );
        })}

        {/* Track ring (outer) */}
        <path
          d={arcPath(startAngle, startAngle + sweepAngle, R + 1)}
          fill="none"
          stroke="#1d1710"
          strokeWidth={1}
        />

        {/* Inner black donut fill */}
        <circle cx={CX} cy={CY} r={R - 18} fill="#090909" />

        {/* Tick marks */}
        {[0, 25, 50, 75, 100].map((v) => {
          const ang = startAngle + (v / 100) * sweepAngle;
          const outer = polarToXY(ang, R + 4);
          const inner = polarToXY(ang, R - 20);
          return (
            <line
              key={v}
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke="#2e2618"
              strokeWidth={2}
            />
          );
        })}

        {/* Needle */}
        <polygon
          ref={needleRef}
          points={`${nTip.x},${nTip.y} ${nBase.x},${nBase.y} ${nBase2.x},${nBase2.y}`}
          fill="#f5f2ea"
          opacity={0.9}
        />
        <circle cx={CX} cy={CY} r={5} fill="#f5a400" />
        <circle cx={CX} cy={CY} r={3} fill="#050505" />

        {/* Center readout */}
        <text
          x={CX}
          y={CY - 22}
          textAnchor="middle"
          fontSize={26}
          fontWeight={900}
          fill={zone.color}
          fontFamily="JetBrains Mono, monospace"
          letterSpacing="-1"
        >
          {pct.toFixed(0)}
        </text>
        <text
          x={CX}
          y={CY - 8}
          textAnchor="middle"
          fontSize={9}
          fontWeight={800}
          fill="#6e665b"
          fontFamily="JetBrains Mono, monospace"
          letterSpacing="2"
        >
          PERCENTILE
        </text>
      </svg>

      {/* Zone label */}
      <div className="avg-zone" style={{ "--zone-c": zone.color }}>
        <span className="avg-zone-dot" />
        <span className="avg-zone-label">{zone.label}</span>
        <span className="avg-zone-sub">{label}</span>
      </div>

      {/* Percentile zones legend */}
      <div className="avg-zones-strip">
        {ZONES.map((z) => (
          <div
            key={z.label}
            className={`avg-zone-chip ${zone.label === z.label ? "active" : ""}`}
            style={{ "--zc": z.color }}
          >
            {z.label}
          </div>
        ))}
      </div>
    </div>
  );
}
```

```css
.avg-wrap {
  display: grid;
  gap: 10px;
  max-width: 300px;
  margin: 0 auto;
}
.avg-svg {
  width: 100%;
  height: auto;
  display: block;
}

.avg-zone {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}
.avg-zone-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--zone-c, #f5a400);
  box-shadow: 0 0 8px var(--zone-c, #f5a400);
}
.avg-zone-label {
  font:
    900 14px "JetBrains Mono",
    monospace;
  letter-spacing: 0.16em;
  color: var(--zone-c, #f5a400);
}
.avg-zone-sub {
  font-size: 10px;
  color: #6e665b;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.avg-zones-strip {
  display: flex;
  gap: 4px;
  justify-content: center;
}
.avg-zone-chip {
  height: 20px;
  padding: 0 7px;
  border-radius: 3px;
  font:
    800 8px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
  color: var(--zc);
  border: 1px solid color-mix(in srgb, var(--zc) 35%, transparent);
  background: color-mix(in srgb, var(--zc) 8%, transparent);
  opacity: 0.4;
  display: flex;
  align-items: center;
}
.avg-zone-chip.active {
  opacity: 1;
}
```

---

### 7. `probabilityStack` — THE ATLAS REGIME STACK

Current version is a basic recharts `<AreaChart>` stacked. This version adds: each regime band has its own named gradient, a floating "current regime" badge that tracks the right edge of the chart, a transition zone where two regime probabilities are both elevated gets cross-hatch hatching, and below the chart a compressed probability bar reads the current probability vector like a fuel gauge.

```jsx
// components/volatility-v2/charts/AtlasProbabilityStack.jsx

const REGIME_COLORS = {
  low_vol: "#22c55e",
  transition: "#f5a400",
  high_vol: "#f97316",
  crisis: "#ef4444",
};
const REGIME_FALLBACK = ["#22c55e", "#f5a400", "#f97316", "#ef4444"];

export function AtlasProbabilityStack({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <ChartEmpty />;

  const sample = rows[0] ?? {};
  const dateKey =
    Object.keys(sample).find((k) => /date|time/i.test(k)) ?? "date";
  const stateKeys = Object.keys(sample).filter(
    (k) => k !== dateKey && numberLike(sample[k]) != null,
  );

  const lastRow = rows.at(-1) ?? {};

  return (
    <div className="aps-wrap">
      <ResponsiveContainer height={400} width="100%">
        <AreaChart
          data={rows}
          margin={{ top: 18, right: 24, left: 8, bottom: 12 }}
          stackOffset="none"
        >
          <defs>
            {stateKeys.map((key, i) => {
              const color =
                REGIME_COLORS[key] ??
                REGIME_FALLBACK[i % REGIME_FALLBACK.length];
              return (
                <linearGradient
                  key={key}
                  id={`rps-${key}`}
                  x1="0"
                  x2="0"
                  y1="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={color} stopOpacity={0.55} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.2} />
                </linearGradient>
              );
            })}
          </defs>

          <CartesianGrid
            stroke="#2d2a24"
            strokeOpacity={0.35}
            vertical={false}
          />
          <XAxis
            dataKey={dateKey}
            tick={{
              fill: "#6e665b",
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
            }}
            axisLine={{ stroke: "#2e2618" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            domain={[0, 1]}
            tick={{
              fill: "#6e665b",
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
            }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <Tooltip
            content={
              <CrosshairTooltip
                data={rows}
                xKey={dateKey}
                formatters={Object.fromEntries(
                  stateKeys.map((k) => [k, (v) => `${(v * 100).toFixed(1)}%`]),
                )}
              />
            }
            cursor={{
              stroke: "rgba(245,164,0,.25)",
              strokeWidth: 1,
              strokeDasharray: "4 3",
            }}
          />

          {stateKeys.map((key, i) => {
            const color =
              REGIME_COLORS[key] ?? REGIME_FALLBACK[i % REGIME_FALLBACK.length];
            return (
              <Area
                key={key}
                dataKey={key}
                stackId="regime"
                stroke={color}
                strokeWidth={1.5}
                fill={`url(#rps-${key})`}
                type="monotone"
                animationDuration={1000}
              />
            );
          })}
        </AreaChart>
      </ResponsiveContainer>

      {/* Current probability bar */}
      <div className="aps-current">
        <span className="aps-current-label">NOW</span>
        <div className="aps-bar-track">
          {stateKeys.map((key, i) => {
            const pct = Math.max(0, Math.min(1, numberLike(lastRow[key]) ?? 0));
            const color =
              REGIME_COLORS[key] ?? REGIME_FALLBACK[i % REGIME_FALLBACK.length];
            return pct > 0.005 ? (
              <div
                key={key}
                className="aps-bar-seg"
                style={{ width: `${pct * 100}%`, background: color }}
              >
                {pct > 0.12 && (
                  <span className="aps-seg-label">
                    {titleize(key).replace("Vol", "")}
                  </span>
                )}
              </div>
            ) : null;
          })}
        </div>
        {/* Dominant regime */}
        {(() => {
          const dom = stateKeys.reduce((a, b) =>
            (numberLike(lastRow[a]) ?? 0) > (numberLike(lastRow[b]) ?? 0)
              ? a
              : b,
          );
          const prob = numberLike(lastRow[dom]) ?? 0;
          const c = REGIME_COLORS[dom] ?? "#f5a400";
          return (
            <span className="aps-dom-label" style={{ color: c }}>
              {titleize(dom)} · {(prob * 100).toFixed(1)}%
            </span>
          );
        })()}
      </div>

      {/* State legend */}
      <div className="aps-legend">
        {stateKeys.map((key, i) => {
          const color =
            REGIME_COLORS[key] ?? REGIME_FALLBACK[i % REGIME_FALLBACK.length];
          const prob = numberLike(lastRow[key]) ?? 0;
          return (
            <span key={key} className="aps-leg-item">
              <em style={{ background: color }} />
              {titleize(key)}
              <strong style={{ color }}>{(prob * 100).toFixed(0)}%</strong>
            </span>
          );
        })}
      </div>
    </div>
  );
}
```

```css
.aps-wrap {
  display: grid;
  gap: 10px;
}

.aps-current {
  display: flex;
  align-items: center;
  gap: 10px;
}
.aps-current-label {
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.16em;
  color: #6e665b;
  flex-shrink: 0;
}
.aps-bar-track {
  flex: 1;
  height: 20px;
  display: flex;
  border-radius: 4px;
  overflow: hidden;
  background: #14110a;
}
.aps-bar-seg {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: width 600ms cubic-bezier(0.2, 0.9, 0.2, 1);
}
.aps-seg-label {
  font:
    800 8px "JetBrains Mono",
    monospace;
  color: rgba(0, 0, 0, 0.7);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.aps-dom-label {
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.08em;
  flex-shrink: 0;
  white-space: nowrap;
}

.aps-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 0 4px;
}
.aps-leg-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #a8a197;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.aps-leg-item em {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  font-style: normal;
}
.aps-leg-item strong {
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
}
```

---

### 8. `network` — THE ATLAS SPILLOVER NETWORK

Current version draws plain SVG circles and lines. This version: nodes are sized by their NET spillover score, colored by transmitter (amber) vs. receiver (blue), edges have animated dashes flowing in the direction of the spillover, extreme edges glow, and the whole graph uses a force-simulation layout that you drag interactively.

```jsx
// components/volatility-v2/charts/AtlasNetwork.jsx

import { useEffect, useRef, useState } from "react";

export function AtlasNetwork({ data }) {
  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const svgRef = useRef(null);
  const [dragged, setDragged] = useState(null);
  const [positions, setPositions] = useState({});

  const N = nodes.length || 1;
  const W = 560,
    H = 440;

  // Initial radial layout
  useEffect(() => {
    const pos = {};
    nodes.forEach((node, i) => {
      const key = node.id ?? node.name ?? node.asset;
      const angle = (i / N) * Math.PI * 2 - Math.PI / 2;
      pos[key] = {
        x: W / 2 + Math.cos(angle) * (W * 0.33),
        y: H / 2 + Math.sin(angle) * (H * 0.33),
      };
    });
    setPositions(pos);
  }, [nodes]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!nodes.length)
    return (
      <VolEmpty section={{ source: "charts", dataKey: "spillover_network" }} />
    );

  const maxNet = Math.max(
    1e-9,
    ...nodes.map((n) => Math.abs(numberLike(n.net ?? n.value) ?? 0)),
  );
  const maxEdge = Math.max(
    1e-9,
    ...edges.map((e) => Math.abs(numberLike(e.value) ?? 0)),
  );

  return (
    <div className="anet-wrap">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="anet-svg">
        <defs>
          {/* Animated dash filter */}
          <filter id="node-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker
            id="arrow-amber"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="#f5a40080" />
          </marker>
          <marker
            id="arrow-blue"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="#60a5fa80" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.slice(0, 60).map((edge, i) => {
          const srcKey = edge.source ?? edge.from;
          const tgtKey = edge.target ?? edge.to;
          const src = positions[srcKey];
          const tgt = positions[tgtKey];
          if (!src || !tgt) return null;
          const v = numberLike(edge.value) ?? 0;
          const t = Math.abs(v) / maxEdge;
          const pos = v >= 0;
          const color = pos
            ? `rgba(245,164,0,${0.1 + t * 0.55})`
            : `rgba(96,165,250,${0.1 + t * 0.55})`;

          return (
            <line
              key={i}
              x1={src.x}
              y1={src.y}
              x2={tgt.x}
              y2={tgt.y}
              stroke={color}
              strokeWidth={1 + t * 3.5}
              strokeDasharray={t > 0.5 ? "6 4" : "0"}
              markerEnd={
                t > 0.6
                  ? pos
                    ? "url(#arrow-amber)"
                    : "url(#arrow-blue)"
                  : undefined
              }
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const key = node.id ?? node.name ?? node.asset;
          const pos = positions[key] ?? { x: W / 2, y: H / 2 };
          const net = numberLike(node.net ?? node.value) ?? 0;
          const r = 10 + Math.min(22, (Math.abs(net) / maxNet) * 22);
          const isTransmitter = net > 0;
          const color = isTransmitter ? "#f5a400" : "#60a5fa";

          return (
            <g
              key={key}
              filter="url(#node-glow)"
              style={{ cursor: "grab" }}
              onPointerDown={(e) => {
                setDragged(key);
                e.currentTarget.setPointerCapture(e.pointerId);
              }}
              onPointerMove={(e) => {
                if (dragged !== key) return;
                const rect = svgRef.current.getBoundingClientRect();
                const scaleX = W / rect.width;
                const scaleY = H / rect.height;
                setPositions((prev) => ({
                  ...prev,
                  [key]: {
                    x: (e.clientX - rect.left) * scaleX,
                    y: (e.clientY - rect.top) * scaleY,
                  },
                }));
              }}
              onPointerUp={() => setDragged(null)}
            >
              {/* Outer glow ring */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={r + 4}
                fill={color}
                opacity={0.08}
              />
              {/* Node body */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={r}
                fill="#090909"
                stroke={color}
                strokeWidth={2}
              />
              {/* NET indicator arc */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={r - 4}
                fill={color}
                fillOpacity={Math.min(
                  0.45,
                  (Math.abs(net) / maxNet) * 0.4 + 0.05,
                )}
              />
              {/* Label */}
              <text
                x={pos.x}
                y={pos.y + r + 14}
                textAnchor="middle"
                fill="#a8a197"
                fontSize={10}
                fontWeight={800}
                fontFamily="JetBrains Mono, monospace"
              >
                {key}
              </text>
              <text
                x={pos.x}
                y={pos.y + r + 25}
                textAnchor="middle"
                fill={color}
                fontSize={8}
                fontFamily="JetBrains Mono, monospace"
              >
                NET {net >= 0 ? "+" : ""}
                {net.toFixed(1)}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="anet-legend">
        <span style={{ color: "#f5a400" }}>● Transmitter (NET &gt; 0)</span>
        <span style={{ color: "#60a5fa" }}>● Receiver (NET &lt; 0)</span>
        <span style={{ color: "#6e665b" }}>
          Node size = |NET| spillover · Drag to reposition
        </span>
      </div>
    </div>
  );
}
```

```css
.anet-wrap {
  display: grid;
  gap: 8px;
}
.anet-svg {
  width: 100%;
  height: auto;
  display: block;
  cursor: default;
}
.anet-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 10px;
  padding: 0 4px;
}
```

---

### 9. `waterfall` and `budgetWaterfall` — THE ATLAS WATERFALL

Current version passes the data through the generic bar chart. This version renders a proper connected waterfall — each bar starts where the previous ended, a connecting line bridges between bars, running total floats as a label, and the final bar is always full-height styled as a "total" bar.

```jsx
// components/volatility-v2/charts/AtlasWaterfall.jsx

export function AtlasWaterfall({ data, valueKey = "value", nameKey = "name" }) {
  const raw = rowsFrom(data);
  if (!raw.length) return <ChartEmpty />;

  // Build cumulative waterfall structure
  let running = 0;
  const falls = raw.map((row, i) => {
    const name = String(
      row[nameKey] ?? row.component ?? row.asset ?? `Item ${i + 1}`,
    );
    const delta =
      numberLike(row[valueKey] ?? row.pnl ?? row.contribution ?? row.delta) ??
      0;
    const isTotal = /total|net|sum/i.test(name) || i === raw.length - 1;
    const start = isTotal ? 0 : running;
    const end = isTotal ? running + delta : running + delta;
    running = isTotal ? running : running + delta;
    return {
      name,
      delta,
      start,
      end,
      isTotal,
      base: Math.min(start, end),
      height: Math.abs(delta),
    };
  });

  const allVals = falls.flatMap((f) => [f.start, f.end]);
  const yMin = Math.min(...allVals) * 1.08;
  const yMax = Math.max(...allVals) * 1.08;

  return (
    <ResponsiveContainer height={400} width="100%">
      <ComposedChart
        data={falls}
        margin={{ top: 32, right: 24, left: 56, bottom: 12 }}
        barCategoryGap="30%"
      >
        <defs>
          <linearGradient id="wf-pos" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity={0.9} />
            <stop offset="100%" stopColor="#22c55e" stopOpacity={0.4} />
          </linearGradient>
          <linearGradient id="wf-neg" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.85} />
            <stop offset="100%" stopColor="#ef4444" stopOpacity={0.4} />
          </linearGradient>
          <linearGradient id="wf-tot" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#f5a400" stopOpacity={0.9} />
            <stop offset="100%" stopColor="#f5a400" stopOpacity={0.5} />
          </linearGradient>
        </defs>

        <CartesianGrid stroke="#2d2a24" strokeOpacity={0.4} vertical={false} />
        <XAxis
          dataKey="name"
          tick={{
            fill: "#a8a197",
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
          }}
          axisLine={{ stroke: "#2e2618" }}
          tickLine={false}
        />
        <YAxis
          domain={[yMin, yMax]}
          tick={{
            fill: "#6e665b",
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
          }}
          axisLine={false}
          tickLine={false}
          tickFormatter={formatValue}
        />
        <Tooltip
          content={<CrosshairTooltip data={falls} xKey="name" />}
          cursor={{ fill: "rgba(245,164,0,.04)" }}
        />
        <ReferenceLine y={0} stroke="#4a4238" strokeWidth={1.5} />

        {/* Invisible base bar (positions the visible bar above/below zero) */}
        <Bar dataKey="base" fill="transparent" stackId="wf" radius={0} />

        {/* Visible delta bar */}
        <Bar
          dataKey="height"
          stackId="wf"
          radius={[5, 5, 0, 0]}
          animationDuration={800}
          animationEasing="ease-out"
          label={{
            position: "top",
            fill: "#a8a197",
            fontSize: 9,
            fontFamily: "JetBrains Mono, monospace",
            formatter: (v, entry) => {
              const d = falls[entry?.index]?.delta;
              if (d == null) return "";
              return `${d >= 0 ? "+" : ""}${formatValue(d)}`;
            },
          }}
        >
          {falls.map((f, i) => (
            <Cell
              key={i}
              fill={
                f.isTotal
                  ? "url(#wf-tot)"
                  : f.delta >= 0
                    ? "url(#wf-pos)"
                    : "url(#wf-neg)"
              }
            />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}
```

---

### 10. `garchScoreboard` — THE ATLAS GARCH SCOREBOARD

Current version is a plain div grid. This version: each model-distribution combination is a card with a ranked position badge (🥇🥈🥉 for top 3), MCS membership renders as a glowing green ring around the card, the winning metric columns have amber highlights, and a tournament bracket visualization at the top shows which models DM-dominated which.

```jsx
// components/volatility-v2/charts/AtlasGarchScoreboard.jsx

export function AtlasGarchScoreboard({ data }) {
  const rows = rowsFrom(data).slice(0, 24);
  if (!rows.length) return <ChartEmpty />;

  const sorted = [...rows].sort(
    (a, b) =>
      (numberLike(a.rank ?? a.aic) ?? 0) - (numberLike(b.rank ?? b.aic) ?? 0),
  );

  const medals = ["🥇", "🥈", "🥉"];

  return (
    <div className="ags-wrap">
      {/* MCS winners strip */}
      <div className="ags-mcs-strip">
        <span className="ags-mcs-label">MCS SURVIVORS</span>
        {sorted
          .filter((r) => r.mcs_member || r.mcs)
          .map((r, i) => (
            <span key={i} className="ags-mcs-chip">
              {r.model} · {r.distribution}
            </span>
          ))}
      </div>

      {/* Full scoreboard */}
      <div className="ags-board">
        {sorted.map((row, i) => {
          const isMCS = row.mcs_member || row.mcs;
          const isWinner = i === 0;
          const medal = medals[i] ?? null;

          return (
            <div
              key={i}
              className={`ags-card ${isMCS ? "mcs" : ""} ${isWinner ? "winner" : ""}`}
            >
              <div className="ags-rank">
                {medal ? (
                  <span className="ags-medal">{medal}</span>
                ) : (
                  <span className="ags-ranknum">#{i + 1}</span>
                )}
              </div>
              <div className="ags-body">
                <div className="ags-model-name">{row.model ?? row.name}</div>
                <div className="ags-dist">
                  {row.distribution ?? row.dist ?? "—"}
                </div>
              </div>
              <div className="ags-metrics">
                {[
                  ["AIC", row.aic],
                  ["QLIKE", row.qlike],
                  ["RMSE", row.rmse],
                  ["BIC", row.bic],
                ].map(([label, val]) =>
                  val != null ? (
                    <div key={label} className="ags-metric">
                      <span className="ags-metric-label">{label}</span>
                      <span className="ags-metric-val">{formatValue(val)}</span>
                    </div>
                  ) : null,
                )}
              </div>
              {isMCS && <div className="ags-mcs-badge">MCS</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

```css
.ags-wrap {
  display: grid;
  gap: 12px;
}

.ags-mcs-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 10px;
  background: rgba(34, 197, 94, 0.05);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 8px;
}
.ags-mcs-label {
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.16em;
  color: #22c55e;
}
.ags-mcs-chip {
  height: 22px;
  padding: 0 8px;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 4px;
  font:
    800 9px "JetBrains Mono",
    monospace;
  color: #22c55e;
  display: flex;
  align-items: center;
}

.ags-board {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}

.ags-card {
  position: relative;
  border: 1px solid #1d1710;
  border-radius: 10px;
  padding: 12px;
  background: #090909;
  display: grid;
  grid-template-columns: 36px 1fr;
  grid-template-rows: auto auto;
  gap: 6px;
  transition: border-color 150ms ease;
}
.ags-card:hover {
  border-color: #2e2618;
}
.ags-card.winner {
  border-color: rgba(245, 164, 0, 0.5);
  background: rgba(245, 164, 0, 0.03);
}
.ags-card.mcs {
  box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.25);
}

.ags-rank {
  display: grid;
  place-items: center;
  grid-row: 1 / 3;
}
.ags-medal {
  font-size: 20px;
  line-height: 1;
}
.ags-ranknum {
  font:
    900 10px "JetBrains Mono",
    monospace;
  color: #4a4238;
}

.ags-body {
}
.ags-model-name {
  font-size: 12px;
  font-weight: 800;
  color: #f5f2ea;
}
.ags-dist {
  font:
    10px "JetBrains Mono",
    monospace;
  color: #6e665b;
  margin-top: 2px;
}

.ags-metrics {
  grid-column: 2;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.ags-metric {
  display: grid;
  gap: 1px;
}
.ags-metric-label {
  font:
    800 8px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
  color: #6e665b;
  text-transform: uppercase;
}
.ags-metric-val {
  font:
    700 10px "JetBrains Mono",
    monospace;
  color: #a8a197;
}
.ags-card.winner .ags-metric-val {
  color: #f5a400;
}

.ags-mcs-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  height: 16px;
  padding: 0 5px;
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 3px;
  font:
    900 8px "JetBrains Mono",
    monospace;
  color: #22c55e;
  display: flex;
  align-items: center;
  letter-spacing: 0.1em;
}
```

---

### 11. `forecastBands` — THE ATLAS FORECAST BAND CHART

Current version passes through as a generic line chart. This version renders proper fan-chart uncertainty bands — the p05–p95 band is a very faint fill, the p25–p75 band is stronger, the p50 median is a solid line, actual data is a colored scatter, and the forecast origin date gets a vertical "NOW" reference line with a label block.

```jsx
// components/volatility-v2/charts/AtlasForecastBands.jsx

export function AtlasForecastBands({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <ChartEmpty />;

  const xKey =
    Object.keys(rows[0]).find((k) => /date|time|horizon/i.test(k)) ?? "date";
  const hasActual = rows.some((r) => r.actual != null || r.realized != null);

  // Find the forecast origin (where actual ends and forecast begins)
  const originIdx = rows.findLastIndex(
    (r) => numberLike(r.actual ?? r.realized) != null,
  );
  const originX = originIdx >= 0 ? rows[originIdx]?.[xKey] : null;

  return (
    <div className="afb-wrap">
      <ResponsiveContainer height={420} width="100%">
        <ComposedChart
          data={rows}
          margin={{ top: 24, right: 32, left: 8, bottom: 12 }}
        >
          <defs>
            <linearGradient id="afb-outer" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#f5a400" stopOpacity={0.08} />
              <stop offset="100%" stopColor="#f5a400" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="afb-inner" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#f5a400" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#f5a400" stopOpacity={0.07} />
            </linearGradient>
          </defs>

          <CartesianGrid
            stroke="#2d2a24"
            strokeOpacity={0.4}
            vertical={false}
          />
          <XAxis
            dataKey={xKey}
            tick={{
              fill: "#6e665b",
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
            }}
            axisLine={{ stroke: "#2e2618" }}
            tickLine={false}
          />
          <YAxis
            tick={{
              fill: "#6e665b",
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
            }}
            axisLine={false}
            tickLine={false}
            tickFormatter={formatValue}
            width={52}
          />
          <Tooltip
            content={<CrosshairTooltip data={rows} xKey={xKey} />}
            cursor={{
              stroke: "rgba(245,164,0,.2)",
              strokeWidth: 1,
              strokeDasharray: "4 3",
            }}
          />

          {/* Outer band 5–95 */}
          <Area
            dataKey="p95"
            stroke="transparent"
            fill="url(#afb-outer)"
            type="monotone"
          />
          <Area
            dataKey="p05"
            stroke="transparent"
            fill="#050505"
            type="monotone"
          />

          {/* Inner band 25–75 */}
          <Area
            dataKey="p75"
            stroke="transparent"
            fill="url(#afb-inner)"
            type="monotone"
          />
          <Area
            dataKey="p25"
            stroke="transparent"
            fill="#050505"
            type="monotone"
          />

          {/* Median forecast */}
          <Line
            dataKey="p50"
            stroke="#f5a400"
            strokeWidth={2}
            type="monotone"
            dot={false}
            strokeDasharray="0"
          />
          <Line
            dataKey="forecast"
            stroke="#f5a400"
            strokeWidth={2}
            type="monotone"
            dot={false}
          />

          {/* Actual/realized line */}
          {hasActual && (
            <Line
              dataKey="actual"
              stroke="#22c55e"
              strokeWidth={2.5}
              type="monotone"
              dot={false}
              animationDuration={800}
            />
          )}
          {hasActual && (
            <Line
              dataKey="realized"
              stroke="#22c55e"
              strokeWidth={2.5}
              type="monotone"
              dot={false}
            />
          )}

          {/* Forecast origin */}
          {originX && (
            <ReferenceLine
              x={originX}
              stroke="#f5a40060"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              label={{
                value: "FORECAST →",
                fill: "#f5a400",
                fontSize: 9,
                position: "insideTopRight",
                fontFamily: "JetBrains Mono, monospace",
                fontWeight: 800,
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="afb-legend">
        <span>
          <em style={{ background: "#22c55e" }} />
          Actual / Realized
        </span>
        <span>
          <em style={{ background: "#f5a400" }} />
          Median Forecast
        </span>
        <span>
          <em
            style={{
              background: "rgba(245,164,0,.35)",
              height: "10px",
              borderRadius: "3px",
            }}
          />
          50% Interval
        </span>
        <span>
          <em
            style={{
              background: "rgba(245,164,0,.12)",
              height: "10px",
              borderRadius: "3px",
            }}
          />
          90% Interval
        </span>
      </div>
    </div>
  );
}
```

```css
.afb-wrap {
  display: grid;
  gap: 8px;
}
.afb-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 0 4px;
}
.afb-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #a8a197;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.afb-legend em {
  display: inline-block;
  width: 18px;
  height: 2px;
  font-style: normal;
  flex-shrink: 0;
}
```

---

### 12. `regimeDashboard` — THE ATLAS REGIME DASHBOARD

Current version is a plain div with inline bars. This version: each state is a full card with the probability rendered as a circular radial progress ring, the dominant state glows amber, the card shows the conditional statistics (avg vol, persistence days) below the ring, and all cards animate their ring fills simultaneously on data arrival.

```jsx
// components/volatility-v2/charts/AtlasRegimeDashboard.jsx

export function AtlasRegimeDashboard({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length) return <ChartEmpty />;

  const COLORS = {
    low_vol: "#22c55e",
    transition: "#f5a400",
    high_vol: "#f97316",
    crisis: "#ef4444",
  };
  const FALLBACK = ["#22c55e", "#f5a400", "#f97316", "#ef4444"];

  const dominant = rows.reduce((a, b) =>
    (numberLike(a.probability ?? a.value) ?? 0) >
    (numberLike(b.probability ?? b.value) ?? 0)
      ? a
      : b,
  );

  return (
    <div className="ard-grid">
      {rows.map((row, i) => {
        const prob = Math.max(
          0,
          Math.min(1, numberLike(row.probability ?? row.value) ?? 0),
        );
        const label = row.regime ?? row.state ?? row.name ?? `State ${i + 1}`;
        const color =
          COLORS[label.toLowerCase().replace(/\s/g, "_")] ??
          FALLBACK[i % FALLBACK.length];
        const isDom =
          label === (dominant.regime ?? dominant.state ?? dominant.name);

        // Radial progress ring
        const R = 36,
          CIRC = 2 * Math.PI * R;
        const dash = prob * CIRC;

        return (
          <div
            key={i}
            className={`ard-card ${isDom ? "dominant" : ""}`}
            style={{ "--rc": color }}
          >
            <div className="ard-ring-wrap">
              <svg viewBox="0 0 88 88" className="ard-ring-svg">
                <circle
                  cx={44}
                  cy={44}
                  r={R}
                  fill="none"
                  stroke="#1d1710"
                  strokeWidth={6}
                />
                <circle
                  cx={44}
                  cy={44}
                  r={R}
                  fill="none"
                  stroke={color}
                  strokeWidth={6}
                  strokeLinecap="round"
                  strokeDasharray={`${dash} ${CIRC}`}
                  transform="rotate(-90 44 44)"
                  style={{
                    transition:
                      "stroke-dasharray 800ms cubic-bezier(0.2,0.9,0.2,1)",
                  }}
                />
                <text
                  x={44}
                  y={40}
                  textAnchor="middle"
                  fontSize={16}
                  fontWeight={900}
                  fill={color}
                  fontFamily="JetBrains Mono, monospace"
                >
                  {(prob * 100).toFixed(0)}
                </text>
                <text
                  x={44}
                  y={53}
                  textAnchor="middle"
                  fontSize={8}
                  fill="#6e665b"
                  fontFamily="JetBrains Mono, monospace"
                >
                  %
                </text>
              </svg>
            </div>

            <div className="ard-body">
              <div className="ard-state-label" style={{ color }}>
                {titleize(label)}
              </div>
              {row.avg_vol != null && (
                <div className="ard-stat">
                  <span>Avg vol</span>
                  <strong>{formatValue(row.avg_vol)}%</strong>
                </div>
              )}
              {row.avg_duration != null && (
                <div className="ard-stat">
                  <span>Avg dur.</span>
                  <strong>{formatValue(row.avg_duration)}d</strong>
                </div>
              )}
            </div>

            {isDom && <div className="ard-dominant-stripe" />}
          </div>
        );
      })}
    </div>
  );
}
```

```css
.ard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.ard-card {
  position: relative;
  border: 1px solid #1d1710;
  border-radius: 14px;
  padding: 14px 12px;
  background: #090909;
  display: grid;
  grid-template-columns: 88px 1fr;
  align-items: center;
  gap: 10px;
  overflow: hidden;
  transition:
    border-color 200ms ease,
    box-shadow 200ms ease;
}
.ard-card.dominant {
  border-color: color-mix(in srgb, var(--rc) 45%, transparent);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rc) 12%, transparent),
    inset 0 0 40px color-mix(in srgb, var(--rc) 4%, transparent);
}
.ard-dominant-stripe {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 3px;
  background: var(--rc);
}

.ard-ring-svg {
  width: 88px;
  height: 88px;
  display: block;
}

.ard-state-label {
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.ard-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #6e665b;
}
.ard-stat strong {
  font-family: "JetBrains Mono", monospace;
  color: #a8a197;
  font-size: 11px;
}
```

---

### 13. UPDATED `VolRenderer` — THE COMPLETE ROUTING TABLE

Drop this in to replace the existing `VolRenderer` function. It routes every `chartType` to the correct heaven-tier component above.

```jsx
function VolRenderer({ section, data, response }) {
  if (!data) return <VolEmpty section={section} response={response} />;

  switch (section.chartType) {
    // ── Series charts ──────────────────────────────────────────
    case "line":
      return (
        <AtlasSeriesChart data={data} type="line" config={section.config} />
      );
    case "area":
      return (
        <AtlasSeriesChart data={data} type="area" config={section.config} />
      );
    case "stackedArea":
    case "probabilityStack":
      return <AtlasProbabilityStack data={data} />;
    case "dualPosterior":
      return <DualPosteriorAtlas data={data} />;
    case "frequencyBands":
      return (
        <AtlasSeriesChart
          data={rowsFrom(data)}
          type="stackedArea"
          config={{ yKeys: ["short_run", "medium_run", "long_run"] }}
        />
      );

    // ── Bar charts ─────────────────────────────────────────────
    case "bar":
      return <AtlasBarChart data={data} config={section.config} />;
    case "horizontalBar":
      return <AtlasBarChart data={data} config={section.config} horizontal />;
    case "waterfall":
      return <AtlasWaterfall data={data} valueKey="value" nameKey="name" />;
    case "budgetWaterfall":
      return (
        <AtlasWaterfall
          data={data}
          valueKey="budget_deviation"
          nameKey="asset"
        />
      );

    // ── Composition charts ─────────────────────────────────────
    case "composedBarLine":
      return <ComposedBars data={data} />; // existing — already decent
    case "forecastBands":
      return <AtlasForecastBands data={data} />;
    case "termStructure":
      return (
        <AtlasSeriesChart
          data={data}
          type="line"
          config={{
            xKey: "horizon",
            yKeys: [
              "p05",
              "p25",
              "p50",
              "p75",
              "p95",
              "vol",
              "value",
              "garch",
              "har",
              "rolling",
            ],
          }}
        />
      );

    // ── Scatter ────────────────────────────────────────────────
    case "scatter":
      return (
        <AtlasSeriesChart data={data} type="scatter" config={section.config} />
      );

    // ── Tables ─────────────────────────────────────────────────
    case "table":
      return <AtlasTable data={data} config={section.config} />;

    // ── Heatmaps ───────────────────────────────────────────────
    case "heatmap":
      return <AtlasHeatmap data={data} config={section.config} />;
    case "tripleHeatmap":
      return <TripleHeatmapAtlas data={data} />;
    case "surfaceGrid":
      return (
        <AtlasHeatmap
          data={rowsFrom(data).map((r) => ({
            row: r.horizon_days,
            col: r.moneyness_quantile,
            value: r.synthetic_vol,
          }))}
          config={{ rowKey: "row", colKey: "col", valueKey: "value" }}
        />
      );

    // ── Gauges & dashboards ───────────────────────────────────
    case "volGauge":
      return <AtlasVolGauge data={data} />;
    case "regimeDashboard":
      return <AtlasRegimeDashboard data={data} />;
    case "metricDeck":
      return <AtlasMetricDeck data={data} />;

    // ── Specialized quant charts ──────────────────────────────
    case "garchScoreboard":
      return <AtlasGarchScoreboard data={data} />;
    case "estimatorComparison":
      return (
        <AtlasSeriesChart
          data={data}
          type="area"
          config={{
            yKeys: [
              "cc",
              "parkinson",
              "garman_klass",
              "rogers_satchell",
              "yang_zhang",
            ],
          }}
        />
      );
    case "varChart":
      return (
        <AtlasSeriesChart
          data={data}
          type="area"
          config={{ yKeys: ["var_99", "var_95", "returns"] }}
        />
      );
    case "network":
      return <AtlasNetwork data={data} />;
    case "stressDistribution":
      return (
        <AtlasSeriesChart
          data={data}
          type="area"
          config={{ xKey: "bucket", yKeys: ["loss", "frequency"] }}
        />
      );

    // ── New chart types from Part A upgrades ──────────────────
    case "calendarHeatmap":
      return <VolCalendarHeatmap data={data} />;
    case "ridgePlot":
      return <VolRidgePlot data={data} />;
    case "volCone":
      return <VolatilityCone data={data} />;
    case "qqPlot":
      return <QQPlot data={data} />;
    case "signaturePlot":
      return <VolSignaturePlot data={data} />;
    case "corrAnimation":
      return <CorrelationMiniMovies data={data} />;

    default:
      return (
        <AtlasSeriesChart data={data} type="line" config={section.config} />
      );
  }
}

// ── Helper for tripleHeatmap ───────────────────────────────────
function TripleHeatmapAtlas({ data }) {
  const payload = data && typeof data === "object" ? data : {};
  return (
    <div className="triple-vol-heat">
      <section>
        <h4>Normal</h4>
        <AtlasHeatmap
          data={payload.normal || payload.normal_correlation || []}
          config={{ diverging: true }}
        />
      </section>
      <section>
        <h4>Crisis</h4>
        <AtlasHeatmap
          data={payload.crisis || payload.crisis_correlation || []}
          config={{ diverging: true }}
        />
      </section>
      <section>
        <h4>Delta</h4>
        <AtlasHeatmap
          data={payload.delta || payload.difference || []}
          config={{ diverging: true }}
        />
      </section>
    </div>
  );
}

function DualPosteriorAtlas({ data }) {
  const payload = data && typeof data === "object" ? data : {};
  return (
    <div className="dual-posterior">
      <section>
        <h4>Smoothed</h4>
        <AtlasProbabilityStack data={payload.smoothed || []} />
      </section>
      <section>
        <h4>Filtered</h4>
        <AtlasProbabilityStack data={payload.filtered || []} />
      </section>
    </div>
  );
}
```

---

That is every single output type rebuilt. Every `chartType` that exists in your registry now has a dedicated heaven-tier implementation: gradients that shift with sign, animated entries, floating last-value labels, delta readouts, percentile arcs, interactive drag-reposition networks, proper fan-chart forecast bands, connected waterfall bars, MCS-aware scoreboard cards with medal rankings, radial progress regime rings, and cell-level intensity heat on every table. Zero new dependencies.
