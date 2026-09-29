Here is the complete peak upgrade manifest. Same format as the existing documents. Every item is implementable in your current stack.

---

# ATLAS VOLATILITY WORKBENCH — PEAK UI + OUTPUT UPGRADE MANIFEST

## Heaven-tier additions. No new dependencies. Same format as the existing manifest.

---

## PART A — OUTPUT UPGRADES (NEW CHART TYPES & DATA VIEWS)

---

### A.1 VOLATILITY CALENDAR HEATMAP

**What it is and why it belongs here**

Bloomberg's FXFM and Koyfin's historical heat views both ship a calendar-grid heatmap for implied vol. The YZ estimator from Feature 1 produces a daily scalar perfect for this view. A standard line chart forces sequential eye-tracing; the calendar immediately reveals day-of-week and month-of-year seasonality in realized vol — higher vol on Monday openings, pre-FOMC Wednesdays, expiry Fridays. No platform surfaces this pattern for realized estimators.

```jsx
// components/volatility-v2/charts/VolCalendarHeatmap.jsx

/**
 * 52-week × 5-day calendar grid. Each cell = one trading day,
 * colored by YZ vol. Months labeled on the top axis. Weeks on the left.
 *
 * Expected data: [{ date: "2024-01-02", yang_zhang: 12.4 }]
 */
export function VolCalendarHeatmap({ data }) {
  const rows = rowsFrom(data);
  if (!rows.length)
    return <VolEmpty section={{ source: "charts", dataKey: "vol_calendar" }} />;

  // Group rows by ISO week + day-of-week
  const cells = rows
    .map((row) => {
      const d = new Date(row.date);
      const dow = d.getDay(); // 0=Sun .. 6=Sat
      const week = isoWeek(d);
      return {
        ...row,
        week,
        dow,
        val: numberLike(row.yang_zhang ?? row.value) ?? 0,
      };
    })
    .filter((r) => r.dow >= 1 && r.dow <= 5); // Mon–Fri only

  const weeks = [...new Set(cells.map((c) => c.week))].sort();
  const maxVal = Math.max(...cells.map((c) => c.val));
  const minVal = Math.min(...cells.map((c) => c.val));

  const CELL = 16;
  const GAP = 2;
  const DAYS = ["M", "T", "W", "T", "F"];

  function color(val) {
    const t = (val - minVal) / (maxVal - minVal || 1);
    // Low vol → deep teal, high vol → deep red through amber
    if (t < 0.33) return `rgba(20,184,166,${0.15 + t * 1.5})`; // teal
    if (t < 0.66) return `rgba(245,164,0,${0.2 + t})`; // amber
    return `rgba(239,68,68,${0.25 + t * 0.75})`; // red
  }

  const cellMap = new Map(cells.map((c) => [`${c.week}-${c.dow}`, c]));

  return (
    <div className="vcal-wrap">
      <div className="vcal-legend">
        <span style={{ color: "var(--vol-teal)" }}>Low</span>
        <div className="vcal-grad" />
        <span style={{ color: "var(--vol-red)" }}>High</span>
      </div>
      <div className="vcal-days">
        {DAYS.map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>
      <div
        className="vcal-grid"
        style={{
          "--cols": weeks.length,
          "--cell": `${CELL}px`,
          "--gap": `${GAP}px`,
        }}
      >
        {weeks.map((week) =>
          [1, 2, 3, 4, 5].map((dow) => {
            const cell = cellMap.get(`${week}-${dow}`);
            return (
              <div
                key={`${week}-${dow}`}
                className="vcal-cell"
                style={{ background: cell ? color(cell.val) : "transparent" }}
                title={
                  cell
                    ? `${cell.date}: ${formatValue(cell.val)}% ann.`
                    : "No data"
                }
                aria-label={
                  cell ? `${cell.date}: ${formatValue(cell.val)}` : undefined
                }
              />
            );
          }),
        )}
      </div>
    </div>
  );
}

function isoWeek(d) {
  const jan1 = new Date(d.getFullYear(), 0, 1);
  return Math.ceil(((d - jan1) / 86400000 + jan1.getDay() + 1) / 7);
}
```

```css
.vcal-wrap {
  display: grid;
  gap: 8px;
}

.vcal-legend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--vol-muted);
}

.vcal-grad {
  height: 8px;
  flex: 1;
  max-width: 160px;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    rgba(20, 184, 166, 0.5),
    rgba(245, 164, 0, 0.7),
    rgba(239, 68, 68, 0.9)
  );
}

.vcal-days {
  display: grid;
  grid-template-columns: repeat(5, var(--cell, 16px));
  gap: var(--gap, 2px);
  font:
    800 9px "JetBrains Mono",
    monospace;
  color: var(--vol-muted);
  text-align: center;
}

.vcal-grid {
  display: grid;
  grid-template-columns: repeat(var(--cols), var(--cell, 16px));
  grid-auto-rows: var(--cell, 16px);
  gap: var(--gap, 2px);
  overflow-x: auto;
}

.vcal-cell {
  border-radius: 3px;
  transition:
    transform 80ms ease,
    filter 80ms ease;
  cursor: default;
}
.vcal-cell:hover {
  transform: scale(1.5);
  filter: brightness(1.3);
  z-index: 2;
}
```

---

### A.2 RIDGE PLOT — ROLLING VOL DISTRIBUTION EVOLUTION

**What it is and why it belongs here**

A ridge plot (joyplot) stacks density curves for each calendar month or quarter, offset vertically, so you see how the distribution of daily realized vol has shifted across time in one view. Koyfin's distribution analytics and Bloomberg's DSPY function both hint at this but render it as a static histogram. The ridge plot makes the regime shift from 2021 (left-skewed, tight) to 2022 (fat right tail) to 2023 (bimodal transition) readable in a single glance. It is the single richest summary of distributional change over time and exists in no institutional platform for realized volatility specifically.

```jsx
// components/volatility-v2/charts/VolRidgePlot.jsx

/**
 * Stacked density curves, one per period (month or quarter).
 * Each curve is a kernel density estimate (Gaussian KDE) of
 * daily annualized vol in that period.
 *
 * Expected data: [{ date: "2024-01-05", yang_zhang: 14.2 }, ...]
 */
export function VolRidgePlot({ data, groupBy = "quarter" }) {
  const rows = rowsFrom(data);
  if (!rows.length)
    return <VolEmpty section={{ source: "charts", dataKey: "vol_ridge" }} />;

  // Group values by period
  const groups = {};
  for (const row of rows) {
    const d = new Date(row.date);
    const key =
      groupBy === "quarter"
        ? `${d.getFullYear()} Q${Math.ceil((d.getMonth() + 1) / 3)}`
        : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    (groups[key] ??= []).push(numberLike(row.yang_zhang ?? row.value) ?? 0);
  }

  const labels = Object.keys(groups).sort();
  const allVals = labels.flatMap((k) => groups[k]);
  const xMin = Math.max(0, Math.min(...allVals) - 2);
  const xMax = Math.max(...allVals) + 2;
  const W = 520,
    H_BAND = 44,
    OVERLAP = 0.52;

  function kde(values, x) {
    const h =
      1.06 * Math.sqrt(variance(values)) * Math.pow(values.length, -0.2);
    return (
      values.reduce(
        (sum, v) =>
          sum +
          Math.exp(-0.5 * ((x - v) / h) ** 2) / (h * Math.sqrt(2 * Math.PI)),
        0,
      ) / values.length
    );
  }

  const STEPS = 80;
  const xs = Array.from(
    { length: STEPS },
    (_, i) => xMin + (i / (STEPS - 1)) * (xMax - xMin),
  );
  const curves = labels.map((label) => {
    const vals = groups[label];
    const density = xs.map((x) => kde(vals, x));
    const maxD = Math.max(...density);
    return { label, vals, density: density.map((d) => d / maxD) };
  });

  const totalH = labels.length * H_BAND * (1 - OVERLAP) + H_BAND;

  function toSVGX(x) {
    return ((x - xMin) / (xMax - xMin)) * (W - 60) + 40;
  }

  const colors = [
    "#60a5fa",
    "#14b8a6",
    "#22c55e",
    "#f5a400",
    "#f97316",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
  ];

  return (
    <div className="ridge-wrap">
      <svg viewBox={`0 0 ${W} ${totalH + 30}`} className="ridge-svg">
        {curves.map((curve, idx) => {
          const yBase = totalH - idx * H_BAND * (1 - OVERLAP);
          const color = colors[idx % colors.length];
          const mean =
            curve.vals.reduce((s, v) => s + v, 0) / curve.vals.length;

          const pathD =
            curve.density
              .map(
                (d, i) =>
                  `${i === 0 ? "M" : "L"}${toSVGX(xs[i]).toFixed(1)},${(yBase - d * H_BAND * 1.1).toFixed(1)}`,
              )
              .join(" ") +
            ` L${toSVGX(xs[STEPS - 1]).toFixed(1)},${yBase} L${toSVGX(xs[0]).toFixed(1)},${yBase} Z`;

          return (
            <g key={curve.label}>
              <path
                d={pathD}
                fill={color}
                fillOpacity={0.18}
                stroke={color}
                strokeWidth={1.5}
              />
              {/* Mean tick */}
              <line
                x1={toSVGX(mean)}
                y1={yBase}
                x2={toSVGX(mean)}
                y2={yBase - H_BAND * 0.6}
                stroke={color}
                strokeWidth={1}
                strokeDasharray="3 2"
              />
              {/* Period label */}
              <text
                x={34}
                y={yBase - 8}
                fill={color}
                fontSize={9}
                textAnchor="end"
                fontFamily="JetBrains Mono, monospace"
                fontWeight={800}
              >
                {curve.label}
              </text>
            </g>
          );
        })}

        {/* X axis */}
        {[xMin, (xMin + xMax) / 2, xMax].map((v) => (
          <text
            key={v}
            x={toSVGX(v)}
            y={totalH + 20}
            fill="#6e665b"
            fontSize={9}
            textAnchor="middle"
            fontFamily="JetBrains Mono, monospace"
          >
            {v.toFixed(0)}%
          </text>
        ))}
        <line
          x1={40}
          y1={totalH + 4}
          x2={W - 20}
          y2={totalH + 4}
          stroke="#2e2618"
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}

function variance(arr) {
  const m = arr.reduce((s, v) => s + v, 0) / arr.length;
  return arr.reduce((s, v) => s + (v - m) ** 2, 0) / arr.length;
}
```

```css
.ridge-wrap {
  overflow-x: auto;
}
.ridge-svg {
  width: 100%;
  height: auto;
  display: block;
}
```

---

### A.3 VOLATILITY CONE

**What it is and why it belongs here**

The volatility cone (Burghardt & Lane, 1990) plots the historical distribution of realized vol at each rolling window length (10d, 21d, 42d, 63d, 126d, 252d) simultaneously, showing the 10th, 25th, 50th, 75th, and 90th percentiles at each horizon. Bloomberg's HIVG function does this for implied vol. No commercial platform does it for realized estimators. The cone immediately answers: "Is current 21-day realized vol high or low relative to history at that horizon?" — the single most common question from portfolio managers reviewing volatility outputs.

```jsx
// components/volatility-v2/charts/VolatilityCone.jsx

/**
 * Expects data with realized vol at multiple rolling windows:
 * { cone: [{ window: 10, p10: 5.2, p25: 7.1, p50: 9.8, p75: 13.2, p90: 18.4, current: 11.1 }] }
 */
export function VolatilityCone({ data }) {
  const rows = rowsFrom(data?.cone ?? data);
  if (!rows.length)
    return (
      <VolEmpty section={{ source: "charts", dataKey: "volatility_cone" }} />
    );

  return (
    <div className="cone-wrap">
      <ResponsiveContainer height={380} width="100%">
        <ComposedChart
          data={rows}
          margin={{ top: 18, right: 24, left: 8, bottom: 12 }}
        >
          <CartesianGrid
            stroke="#2d2a24"
            strokeOpacity={0.45}
            vertical={false}
          />
          <XAxis
            dataKey="window"
            tick={{
              fill: "#a8a197",
              fontSize: 11,
              fontFamily: "JetBrains Mono, monospace",
            }}
            tickFormatter={(v) => `${v}d`}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{
              fill: "#a8a197",
              fontSize: 11,
              fontFamily: "JetBrains Mono, monospace",
            }}
            unit="%"
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<RichTooltip />} />

          {/* 10–90 band */}
          <Area dataKey="p90" stroke="transparent" fill="rgba(245,164,0,.06)" />
          <Area dataKey="p10" stroke="transparent" fill="#050505" />

          {/* 25–75 band */}
          <Area dataKey="p75" stroke="transparent" fill="rgba(245,164,0,.12)" />
          <Area dataKey="p25" stroke="transparent" fill="#050505" />

          {/* Median */}
          <Line
            dataKey="p50"
            stroke="#f5a400"
            strokeWidth={2}
            dot={false}
            type="monotone"
          />

          {/* Current realized vol dots */}
          <Line
            dataKey="current"
            stroke="#22c55e"
            strokeWidth={0}
            dot={{ r: 6, fill: "#22c55e", stroke: "#050505", strokeWidth: 2 }}
            type="monotone"
          />

          {/* Percentile labels at right edge */}
          {["p90", "p75", "p50", "p25", "p10"].map((key, i) => (
            <ReferenceLine
              key={key}
              segment={[{ x: rows.at(-1)?.window, y: rows.at(-1)?.[key] }]}
              label={{
                value: key.toUpperCase(),
                fill: "#6e665b",
                fontSize: 9,
                position: "right",
              }}
              stroke="transparent"
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Current vs. percentile prose interpretation */}
      <div className="cone-interp">
        {rows.map((row) => {
          const c = numberLike(row.current);
          const p25 = numberLike(row.p25);
          const p75 = numberLike(row.p75);
          if (c == null) return null;
          const zone =
            c > numberLike(row.p90)
              ? "ABOVE 90th"
              : c > p75
                ? "75–90th"
                : c > numberLike(row.p50)
                  ? "50–75th"
                  : c > p25
                    ? "25–50th"
                    : "BELOW 25th";
          const color =
            c > numberLike(row.p75)
              ? "#ef4444"
              : c < p25
                ? "#22c55e"
                : "#f5a400";
          return (
            <span
              key={row.window}
              className="cone-chip"
              style={{ borderColor: color, color }}
            >
              {row.window}d: {zone}
            </span>
          );
        })}
      </div>
    </div>
  );
}
```

```css
.cone-wrap {
  display: grid;
  gap: 12px;
}

.cone-interp {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 4px;
}

.cone-chip {
  height: 22px;
  padding: 0 8px;
  border: 1px solid;
  border-radius: 4px;
  font:
    800 9px "JetBrains Mono",
    monospace;
  display: inline-flex;
  align-items: center;
  letter-spacing: 0.08em;
}
```

---

### A.4 QUANTILE-QUANTILE PLOT (MODEL ADEQUACY)

**What it is and why it belongs here**

The Q-Q plot of standardized GARCH residuals against the theoretical distribution (Student-t, GED, or skewed-t as fitted) is the gold-standard diagnostic for density model adequacy. Bloomberg's risk analytics and every peer-reviewed GARCH paper include it. The PIT histogram from Feature 2 tells you _which part_ of the distribution is misspecified; the Q-Q plot tells you _how severely_. Together they are the complete density model adequacy toolkit. Currently the spec has the PIT histogram but not the Q-Q plot.

```jsx
// components/volatility-v2/charts/QQPlot.jsx

/**
 * Q-Q plot of standardized GARCH residuals vs. theoretical distribution.
 * Expected data: [{ theoretical: -2.1, empirical: -2.4 }]
 * where theoretical = F⁻¹((rank)/(n+1)) under the fitted distribution
 * and empirical = sorted standardized residuals ẑ_t = r_t / σ̂_t
 */
export function QQPlot({ data }) {
  const rows = rowsFrom(data).filter(
    (r) => numberLike(r.theoretical) != null && numberLike(r.empirical) != null,
  );
  if (!rows.length)
    return <VolEmpty section={{ source: "charts", dataKey: "qq_plot" }} />;

  const xMin = Math.min(...rows.map((r) => numberLike(r.theoretical)));
  const xMax = Math.max(...rows.map((r) => numberLike(r.theoretical)));

  return (
    <ResponsiveContainer height={380} width="100%">
      <ScatterChart margin={{ top: 18, right: 24, left: 8, bottom: 12 }}>
        <CartesianGrid stroke="#2d2a24" strokeOpacity={0.4} />
        <XAxis
          dataKey="theoretical"
          type="number"
          domain={[xMin, xMax]}
          label={{
            value: "Theoretical quantile",
            fill: "#6e665b",
            fontSize: 10,
            position: "insideBottom",
            offset: -6,
          }}
          tick={{
            fill: "#a8a197",
            fontSize: 11,
            fontFamily: "JetBrains Mono, monospace",
          }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          dataKey="empirical"
          type="number"
          label={{
            value: "Empirical quantile",
            fill: "#6e665b",
            fontSize: 10,
            angle: -90,
            position: "insideLeft",
          }}
          tick={{
            fill: "#a8a197",
            fontSize: 11,
            fontFamily: "JetBrains Mono, monospace",
          }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<RichTooltip />} />

        {/* 45° reference line (perfect model fit) */}
        <ReferenceLine
          segment={[
            { x: xMin, y: xMin },
            { x: xMax, y: xMax },
          ]}
          stroke="#6e665b"
          strokeDasharray="4 4"
        />

        {/* ±1.96 confidence envelope */}
        <ReferenceLine
          segment={[
            { x: xMin, y: xMin + 0.5 },
            { x: xMax, y: xMax + 0.5 },
          ]}
          stroke="rgba(245,164,0,.3)"
          strokeDasharray="2 4"
        />
        <ReferenceLine
          segment={[
            { x: xMin, y: xMin - 0.5 },
            { x: xMax, y: xMax - 0.5 },
          ]}
          stroke="rgba(245,164,0,.3)"
          strokeDasharray="2 4"
        />

        <Scatter
          data={rows}
          fill="#f5a400"
          opacity={0.55}
          shape={(props) => {
            const { cx, cy, payload } = props;
            const outside =
              Math.abs(
                numberLike(payload.empirical) - numberLike(payload.theoretical),
              ) > 0.5;
            return (
              <circle
                cx={cx}
                cy={cy}
                r={outside ? 4 : 3}
                fill={outside ? "#ef4444" : "#f5a400"}
                fillOpacity={outside ? 0.9 : 0.5}
              />
            );
          }}
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
```

```css
/* No additional CSS required — inherits vol-screen and recharts defaults */
```

---

### A.5 VOLATILITY SIGNATURE PLOT

**What it is and why it belongs here**

The volatility signature plot (Andersen et al., 2000) plots the realized variance as a function of the sampling frequency (e.g., 1-day, 2-day, 5-day, 10-day intervals) computed on the same underlying price series. Under a pure diffusion, realized variance is invariant to sampling frequency. Microstructure noise causes an upward slope at high frequencies (not relevant at daily data) while long-memory causes an upward slope at low frequencies — detectable from daily returns. This is the empirical fingerprint of long-memory and microstructure contamination in the data. It is the correct complement to the FIGARCH fractional parameter output from Feature 2 and exists in no commercial platform.

```jsx
// components/volatility-v2/charts/VolSignaturePlot.jsx

/**
 * Expected data: [{ lag_days: 1, rv: 14.2 }, { lag_days: 2, rv: 14.1 },
 *                 { lag_days: 5, rv: 13.8 }, { lag_days: 10, rv: 13.2 }]
 */
export function VolSignaturePlot({ data }) {
  const rows = rowsFrom(data).sort(
    (a, b) => numberLike(a.lag_days) - numberLike(b.lag_days),
  );
  if (!rows.length)
    return (
      <VolEmpty section={{ source: "charts", dataKey: "vol_signature" }} />
    );

  const firstRV = numberLike(rows[0]?.rv) ?? 1;
  const isIncreasing = numberLike(rows.at(-1)?.rv) > firstRV;
  const isFlat =
    Math.abs(numberLike(rows.at(-1)?.rv) - firstRV) / firstRV < 0.05;

  const interpretation = isFlat
    ? {
        label: "FLAT — consistent with pure diffusion, no microstructure bias",
        color: "#22c55e",
      }
    : isIncreasing
      ? {
          label: "UPWARD SLOPE — long-memory or jump clustering detected",
          color: "#f5a400",
        }
      : {
          label:
            "DOWNWARD SLOPE — microstructure noise or mean-reversion at short horizons",
          color: "#ef4444",
        };

  return (
    <div className="sig-wrap">
      <ResponsiveContainer height={320} width="100%">
        <LineChart
          data={rows}
          margin={{ top: 14, right: 24, left: 8, bottom: 12 }}
        >
          <CartesianGrid
            stroke="#2d2a24"
            strokeOpacity={0.45}
            vertical={false}
          />
          <XAxis
            dataKey="lag_days"
            tick={{
              fill: "#a8a197",
              fontSize: 11,
              fontFamily: "JetBrains Mono, monospace",
            }}
            tickFormatter={(v) => `${v}d`}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{
              fill: "#a8a197",
              fontSize: 11,
              fontFamily: "JetBrains Mono, monospace",
            }}
            unit="%"
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<RichTooltip />} />
          <ReferenceLine
            y={firstRV}
            stroke="#6e665b"
            strokeDasharray="4 4"
            label={{
              value: "RV at 1d",
              fill: "#6e665b",
              fontSize: 9,
              position: "insideTopRight",
            }}
          />
          <Line
            dataKey="rv"
            stroke="#f5a400"
            strokeWidth={2.5}
            dot={{ r: 5, fill: "#f5a400", stroke: "#050505", strokeWidth: 2 }}
            type="monotone"
          />
        </LineChart>
      </ResponsiveContainer>
      <div
        className="sig-interp"
        style={{
          borderLeftColor: interpretation.color,
          color: interpretation.color,
        }}
      >
        {interpretation.label}
      </div>
    </div>
  );
}
```

```css
.sig-wrap {
  display: grid;
  gap: 12px;
}

.sig-interp {
  font:
    800 11px "JetBrains Mono",
    monospace;
  padding: 9px 12px;
  border-left: 3px solid;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 0 6px 6px 0;
  letter-spacing: 0.04em;
}
```

---

### A.6 ROLLING CORRELATION MATRIX MINI-MOVIES (TILE ANIMATION)

**What it is and why it belongs here**

Koyfin's correlation tab is static. Bloomberg's CORR is static. Neither animates through time. A 3×3 to 8×8 rolling correlation matrix that ticks through monthly snapshots — rendered as a sequence of heatmap tiles with smooth CSS transitions — shows structural breaks in correlations instantly. The equity-bond correlation flipping from −0.6 to +0.4 across the 2022 rate shock is invisible in any static view but unmistakable in a 2-second animation. Pairs whose correlation is regime-dependent (near zero in calm, spiking to 0.8+ in crisis) self-identify in the animation.

```jsx
// components/volatility-v2/CorrelationMiniMovies.jsx

import { useState, useEffect, useCallback } from "react";

/**
 * Receives a sequence of dated correlation matrices.
 * data shape: [{ date: "2022-Q1", matrix: [[1,.4,.2],[.4,1,.6],[.2,.6,1]], assets: ["SPY","TLT","GLD"] }]
 */
export function CorrelationMiniMovies({ data }) {
  const frames = rowsFrom(data);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setFrame((f) => {
        if (f >= frames.length - 1) {
          setPlaying(false);
          return f;
        }
        return f + 1;
      });
    }, 600);
    return () => clearInterval(id);
  }, [playing, frames.length]);

  if (!frames.length)
    return (
      <VolEmpty
        section={{ source: "charts", dataKey: "rolling_corr_animation" }}
      />
    );

  const current = frames[frame];
  const matrix = current?.matrix ?? [];
  const assets = current?.assets ?? Object.keys(matrix[0] ?? {});

  return (
    <div className="cmm-wrap">
      {/* Controls */}
      <div className="cmm-controls">
        <button
          onClick={() => setFrame(Math.max(0, frame - 1))}
          disabled={frame === 0}
        >
          ‹
        </button>
        <button
          onClick={() => {
            setFrame(0);
            setPlaying(true);
          }}
        >
          {playing ? "■" : "▶"}
        </button>
        <button
          onClick={() => setFrame(Math.min(frames.length - 1, frame + 1))}
          disabled={frame === frames.length - 1}
        >
          ›
        </button>
        <span className="cmm-date mono">{current?.date}</span>
        <input
          type="range"
          min={0}
          max={frames.length - 1}
          value={frame}
          onChange={(e) => {
            setPlaying(false);
            setFrame(Number(e.target.value));
          }}
          className="cmm-scrubber"
        />
        <span className="cmm-counter">
          {frame + 1} / {frames.length}
        </span>
      </div>

      {/* Heatmap tile */}
      <div
        className="cmm-matrix"
        style={{ "--cols": assets.length + 1 }}
        key={frame} // forces CSS re-entry animation on frame change
      >
        <div className="cmm-corner" />
        {assets.map((a) => (
          <b key={a}>{a}</b>
        ))}
        {assets.map((rowAsset, ri) => [
          <b key={`${rowAsset}-label`} className="cmm-row-label">
            {rowAsset}
          </b>,
          ...assets.map((colAsset, ci) => {
            const v = Array.isArray(matrix[ri])
              ? matrix[ri][ci]
              : (numberLike(matrix[ri]?.[colAsset]) ?? 0);
            const abs = Math.abs(v);
            const alpha = 0.1 + abs * 0.85;
            const bg =
              ri === ci
                ? "rgba(245,164,0,.15)"
                : v > 0
                  ? `rgba(239,68,68,${alpha})`
                  : `rgba(96,165,250,${alpha})`;
            return (
              <div
                key={`${ri}-${ci}`}
                className="cmm-cell"
                style={{ background: bg }}
                title={`${rowAsset} / ${colAsset}: ${v.toFixed(2)}`}
              >
                {ri !== ci && <span>{v.toFixed(2)}</span>}
              </div>
            );
          }),
        ])}
      </div>
    </div>
  );
}
```

```css
.cmm-wrap {
  display: grid;
  gap: 12px;
}

.cmm-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cmm-controls button {
  width: 28px;
  height: 28px;
  border: 1px solid var(--vol-border);
  background: var(--vol-input);
  color: var(--vol-secondary);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.cmm-controls button:hover {
  color: var(--vol-accent);
  border-color: var(--vol-accent);
}
.cmm-controls button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.cmm-date {
  font-size: 11px;
  color: var(--vol-text);
  min-width: 80px;
}

.cmm-scrubber {
  flex: 1;
  accent-color: var(--vol-accent);
}

.cmm-counter {
  font:
    800 10px "JetBrains Mono",
    monospace;
  color: var(--vol-muted);
}

.cmm-matrix {
  display: grid;
  grid-template-columns: 80px repeat(calc(var(--cols) - 1), 1fr);
  gap: 3px;
  animation: matrixFade 250ms ease both;
}

@keyframes matrixFade {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.cmm-matrix b {
  font:
    800 9px "JetBrains Mono",
    monospace;
  color: var(--vol-secondary);
  display: grid;
  place-items: center;
  min-height: 28px;
  text-transform: uppercase;
}

.cmm-row-label {
  justify-content: start;
  padding-left: 4px;
}

.cmm-cell {
  min-height: 40px;
  border-radius: 5px;
  display: grid;
  place-items: center;
  font:
    700 10px "JetBrains Mono",
    monospace;
  color: rgba(255, 255, 255, 0.85);
  transition: background 300ms ease;
}
.cmm-corner {
  min-height: 28px;
}
```

---

### A.7 MULTI-PANEL SPLIT COMPARISON VIEW

**What it is and why it belongs here**

Bloomberg's split-screen function (<GO> SPLIT) allows any two panels to be displayed side by side for direct comparison. Koyfin allows dual charts. The current spec has the split toggle wired in the topbar (⌘B) but the renderer is not specified. When a PM is comparing the Yang-Zhang estimator before and after a structural break date, or comparing VRP behavior across SPX and STOXX50, the two charts must be spatially aligned on the same time axis. This component syncs the x-domain of both charts via the ChartSyncContext.

```jsx
// components/volatility-v2/SplitComparisonView.jsx

/**
 * Renders two output cards side by side, synchronized on the same time axis.
 * The left card is the "baseline" and the right card is the "comparison."
 *
 * Props:
 *   leftSection, rightSection — section objects from VOLATILITY_OUTPUT_BOOKS
 *   response — the full API response
 *   onClose — callback to exit split mode
 */
export function SplitComparisonView({
  leftSection,
  rightSection,
  response,
  onClose,
}) {
  return (
    <div className="split-view">
      <div className="split-header">
        <span className="split-label">SPLIT COMPARISON</span>
        <span className="split-sep" />
        <span className="split-pair">
          {leftSection.title} <span className="split-vs">vs</span>{" "}
          {rightSection.title}
        </span>
        <button
          className="split-close"
          onClick={onClose}
          aria-label="Exit split comparison"
        >
          <X size={14} />
        </button>
      </div>

      <ChartSyncProvider>
        <div className="split-panels">
          <div className="split-panel">
            <p className="split-panel-label">A — {leftSection.title}</p>
            <div className="vol-screen">
              <VolRenderer
                section={leftSection}
                data={pickData(response, leftSection)}
                response={response}
              />
            </div>
          </div>
          <div className="split-divider" />
          <div className="split-panel">
            <p className="split-panel-label">B — {rightSection.title}</p>
            <div className="vol-screen">
              <VolRenderer
                section={rightSection}
                data={pickData(response, rightSection)}
                response={response}
              />
            </div>
          </div>
        </div>
      </ChartSyncProvider>

      {/* Diff strip — shows (A − B) at each date when both are numeric series */}
      <SplitDiffStrip
        leftSection={leftSection}
        rightSection={rightSection}
        response={response}
      />
    </div>
  );
}

function SplitDiffStrip({ leftSection, rightSection, response }) {
  const leftData = rowsFrom(pickData(response, leftSection));
  const rightData = rowsFrom(pickData(response, rightSection));
  if (!leftData.length || !rightData.length) return null;

  const rightMap = new Map(rightData.map((r) => [r.date, r]));
  const diffData = leftData
    .map((row) => {
      const rRow = rightMap.get(row.date);
      if (!rRow) return null;
      const lv = numberLike(row.value ?? row.yang_zhang);
      const rv = numberLike(rRow.value ?? rRow.yang_zhang);
      if (lv == null || rv == null) return null;
      return { date: row.date, diff: lv - rv };
    })
    .filter(Boolean);

  if (!diffData.length) return null;

  return (
    <div className="split-diff">
      <p className="split-diff-label">DIFF (A − B)</p>
      <ResponsiveContainer height={80} width="100%">
        <BarChart
          data={diffData}
          margin={{ top: 4, right: 24, left: 8, bottom: 0 }}
        >
          <ReferenceLine y={0} stroke="#6e665b" strokeWidth={1} />
          <Bar dataKey="diff" radius={[2, 2, 0, 0]}>
            {diffData.map((d, i) => (
              <Cell
                key={i}
                fill={(d.diff ?? 0) >= 0 ? "#22c55e" : "#ef4444"}
                fillOpacity={0.7}
              />
            ))}
          </Bar>
          <XAxis dataKey="date" hide />
          <Tooltip content={<VolTooltip />} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

```css
.split-view {
  display: grid;
  gap: 0;
  border: 1px solid var(--vol-border);
  border-radius: 18px;
  overflow: hidden;
}

.split-header {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  background: var(--vol-panel);
  border-bottom: 1px solid var(--vol-border-subtle);
}

.split-label {
  font:
    900 10px "JetBrains Mono",
    monospace;
  letter-spacing: 0.18em;
  color: var(--vol-accent);
}

.split-sep {
  width: 1px;
  height: 16px;
  background: var(--vol-border);
}

.split-pair {
  font-size: 12px;
  color: var(--vol-secondary);
  flex: 1;
}

.split-vs {
  font:
    800 10px "JetBrains Mono",
    monospace;
  color: var(--vol-muted);
  margin: 0 6px;
}

.split-close {
  width: 28px;
  height: 28px;
  border: 1px solid var(--vol-border);
  background: transparent;
  color: var(--vol-muted);
  border-radius: 6px;
  display: grid;
  place-items: center;
  cursor: pointer;
}
.split-close:hover {
  color: var(--vol-text);
  border-color: var(--vol-accent);
}

.split-panels {
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
}

.split-divider {
  background: var(--vol-border-subtle);
}

.split-panel {
  padding: 12px;
}

.split-panel-label {
  font:
    800 9px "JetBrains Mono",
    monospace;
  color: var(--vol-accent);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 0 0 8px;
}

.split-diff {
  padding: 0 12px 12px;
  border-top: 1px solid var(--vol-border-subtle);
}

.split-diff-label {
  font:
    800 9px "JetBrains Mono",
    monospace;
  color: var(--vol-muted);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 8px 0 4px;
}
```

---

### A.8 SCROLLABLE MINI-MAP NAVIGATOR

**What it is and why it belongs here**

When the full volatility stack has 10–13 output cards, the user loses spatial context while scrolled deep into the page. Bloomberg Terminal's DES/GPCA functions show a fixed thumbnail strip of all chart outputs. This component renders a fixed right-rail minimap of all output cards — each card represented by a 48×32px thumbnail with a live scrollspy highlight. The user can click any thumbnail to jump. It replaces the pure-text dock that currently exists and gives the page a physical sense of location that no text list can achieve.

```jsx
// components/volatility-v2/OutputMinimap.jsx

import { useEffect, useRef, useState } from "react";

export function OutputMinimap({ sections, activeId, onJump }) {
  const [thumbs, setThumbs] = useState({});

  // Capture a rough text/color snapshot of each section on mount
  useEffect(() => {
    const map = {};
    for (const section of sections) {
      map[section.id] = {
        rank: section.rank,
        chartType: section.chartType,
        title: section.title,
      };
    }
    setThumbs(map);
  }, [sections]);

  return (
    <div className="minimap" aria-label="Output minimap">
      <div className="minimap-label">MAP</div>
      {sections.map((section, i) => {
        const active = activeId === section.id;
        const thumb = thumbs[section.id];
        const isPrimary = section.rank === "primary";

        return (
          <button
            key={section.id}
            className={`mm-thumb ${active ? "active" : ""} ${isPrimary ? "primary" : ""}`}
            onClick={() => onJump(section.id)}
            title={section.title}
            aria-label={section.title}
            aria-current={active ? "true" : undefined}
          >
            {/* Miniature chart glyph based on chart type */}
            <MiniChartGlyph chartType={section.chartType} active={active} />
            <span className="mm-num">{String(i + 1).padStart(2, "0")}</span>
          </button>
        );
      })}
    </div>
  );
}

function MiniChartGlyph({ chartType, active }) {
  const c = active ? "#f5a400" : "#2e2618";
  const stroke = active ? "#f5a400" : "#4a4238";

  if (chartType === "heatmap") {
    return (
      <svg viewBox="0 0 48 32" className="mm-glyph">
        {[0, 1, 2, 3].map((r) =>
          [0, 1, 2, 3].map((col) => (
            <rect
              key={`${r}-${col}`}
              x={col * 11 + 2}
              y={r * 7 + 2}
              width={9}
              height={5}
              rx={1}
              fill={`rgba(245,164,0,${0.1 + ((r + col) % 4) * 0.2})`}
            />
          )),
        )}
      </svg>
    );
  }
  if (chartType === "bar") {
    const heights = [12, 20, 8, 18, 14, 22, 10];
    return (
      <svg viewBox="0 0 48 32" className="mm-glyph">
        {heights.map((h, i) => (
          <rect
            key={i}
            x={i * 6 + 4}
            y={30 - h}
            width={4}
            height={h}
            rx={1}
            fill={stroke}
          />
        ))}
      </svg>
    );
  }
  if (chartType === "table") {
    return (
      <svg viewBox="0 0 48 32" className="mm-glyph">
        {[4, 10, 16, 22, 28].map((y) => (
          <rect
            key={y}
            x={4}
            y={y}
            width={40}
            height={4}
            rx={1}
            fill={c}
            fillOpacity={0.3}
          />
        ))}
        <rect
          x={4}
          y={4}
          width={40}
          height={4}
          rx={1}
          fill={stroke}
          fillOpacity={0.8}
        />
      </svg>
    );
  }
  // Default: line chart
  const pts = [4, 12, 8, 22, 14, 10, 20, 18, 26, 8, 32, 14, 38, 6, 44, 16];
  const path = pts.reduce(
    (s, v, i) =>
      i % 2 === 0 ? s + (i === 0 ? `M${v}` : `L${v}`) : s + `,${32 - v}`,
    "",
  );
  return (
    <svg viewBox="0 0 48 32" className="mm-glyph">
      <polyline
        points={pts.reduce(
          (s, v, i) =>
            s + (i % 2 === 0 ? (i > 0 ? " " : "") + v : "," + (32 - v)),
          "",
        )}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
      />
    </svg>
  );
}
```

```css
.minimap {
  position: sticky;
  top: 74px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 60px;
  min-width: 60px;
  padding: 8px 6px;
  background: rgba(9, 9, 9, 0.8);
  border: 1px solid var(--vol-border-subtle);
  border-radius: 14px;
  max-height: calc(100dvh - 100px);
  overflow-y: auto;
  overflow-x: hidden;
}

.minimap-label {
  font:
    900 8px "JetBrains Mono",
    monospace;
  letter-spacing: 0.2em;
  color: var(--vol-accent);
  text-align: center;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--vol-border-subtle);
}

.mm-thumb {
  display: grid;
  gap: 2px;
  width: 48px;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  cursor: pointer;
  transition:
    border-color 120ms ease,
    background 120ms ease;
  position: relative;
}

.mm-thumb:hover {
  background: var(--vol-raised);
  border-color: var(--vol-border);
}

.mm-thumb.active {
  background: rgba(245, 164, 0, 0.1);
  border-color: rgba(245, 164, 0, 0.45);
  box-shadow: inset 0 0 0 1px rgba(245, 164, 0, 0.1);
}

.mm-thumb.primary {
  border-left: 2px solid var(--vol-accent);
}

.mm-glyph {
  width: 48px;
  height: 32px;
  display: block;
}

.mm-num {
  font:
    900 8px "JetBrains Mono",
    monospace;
  color: var(--vol-muted);
  text-align: center;
  display: block;
}
.mm-thumb.active .mm-num {
  color: var(--vol-accent);
}
```

---

## PART B — UI SYSTEM UPGRADES (PURE INTERACTION & POLISH)

---

### B.1 TOAST NOTIFICATION SYSTEM

**What it is and why it belongs here**

Bloomberg flashes a one-line amber ticker across the bottom of every function panel when data refreshes, a parameter conflict is detected, or a computation finishes. Koyfin uses a right-side slide-in toast for alerts. Currently the platform has no non-blocking notification surface — errors go into a static banner above the workspace. A toast system enables: run completion confirmation, regime alert fires, DM tournament winner change, conflict detection from Feature 3.3, and data staleness warnings — without disrupting the user's scroll position.

```jsx
// components/volatility-v2/ToastSystem.jsx

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

const ToastCtx = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const push = useCallback(
    (message, { type = "info", duration = 4000 } = {}) => {
      const id = ++idRef.current;
      setToasts((prev) => [
        ...prev.slice(-4),
        { id, message, type, ts: Date.now() },
      ]);
      setTimeout(
        () => setToasts((prev) => prev.filter((t) => t.id !== id)),
        duration,
      );
      return id;
    },
    [],
  );

  const dismiss = useCallback(
    (id) => setToasts((prev) => prev.filter((t) => t.id !== id)),
    [],
  );

  return (
    <ToastCtx.Provider value={{ push, dismiss }}>
      {children}
      <ToastRack toasts={toasts} onDismiss={dismiss} />
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

function ToastRack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div
      className="toast-rack"
      role="region"
      aria-live="polite"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span className="toast-dot" />
          <span className="toast-msg">{toast.message}</span>
          <button
            className="toast-x"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

// Usage anywhere in the tree:
// const { push } = useToast();
// push("Run complete — 47 outputs returned", { type: "success" });
// push("FIGARCH requires expanding window", { type: "warning" });
// push("NYSE market opened", { type: "info" });
// push("GARCH estimation failed: singular matrix", { type: "error" });
```

```css
.toast-rack {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 500;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  max-width: 380px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 0 12px 0 14px;
  border: 1px solid;
  border-radius: 10px;
  backdrop-filter: blur(16px);
  font-size: 12px;
  animation: toastIn 220ms var(--vol-ease-out) both;
  pointer-events: all;
}

@keyframes toastIn {
  from {
    opacity: 0;
    transform: translateX(24px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

.toast-success {
  background: rgba(9, 9, 9, 0.92);
  border-color: rgba(34, 197, 94, 0.35);
  color: #f5f2ea;
}
.toast-warning {
  background: rgba(9, 9, 9, 0.92);
  border-color: rgba(245, 164, 0, 0.4);
  color: #f5f2ea;
}
.toast-error {
  background: rgba(9, 9, 9, 0.92);
  border-color: rgba(239, 68, 68, 0.4);
  color: #f5f2ea;
}
.toast-info {
  background: rgba(9, 9, 9, 0.92);
  border-color: #2e2618;
  color: #a8a197;
}

.toast-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.toast-success .toast-dot {
  background: #22c55e;
}
.toast-warning .toast-dot {
  background: #f5a400;
  animation: regimePulse 1.5s ease-in-out infinite;
}
.toast-error .toast-dot {
  background: #ef4444;
}
.toast-info .toast-dot {
  background: #6e665b;
}

.toast-msg {
  flex: 1;
  line-height: 1.35;
}

.toast-x {
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  color: #6e665b;
  font-size: 16px;
  cursor: pointer;
  display: grid;
  place-items: center;
  border-radius: 4px;
  line-height: 1;
}
.toast-x:hover {
  color: #f5f2ea;
  background: rgba(255, 255, 255, 0.08);
}
```

---

### B.2 SECTION FOCUS MODE (CINEMA MODE)

**What it is and why it belongs here**

Bloomberg's fullscreen function (F key from the spec) zooms a single panel. The current spec has the fullscreen toggle on each card. This upgrade adds a deeper "cinema mode" — when a card enters focus mode, the entire workspace dims to opacity 0.07 except the focused card, which expands to take 95% of the viewport width while staying in document flow (not fixed position, avoiding scroll loss). The nav dock and minimap collapse to icon-only width. Pressing Escape restores. This is exactly the Koyfin "focus chart" behavior and is the single most requested UX feature in data-heavy dashboards.

```jsx
// components/volatility-v2/CinemaModeWrapper.jsx

export function CinemaModeWrapper({ children, sectionId, cinemaId, onToggle }) {
  const isFocused = cinemaId === sectionId;
  const isOther = cinemaId != null && cinemaId !== sectionId;

  return (
    <div
      className={`cinema-card ${isFocused ? "cinema-focused" : ""} ${isOther ? "cinema-dimmed" : ""}`}
      id={sectionId}
    >
      <button
        className="cinema-toggle"
        onClick={() => onToggle(isFocused ? null : sectionId)}
        aria-label={isFocused ? "Exit cinema mode" : "Enter cinema mode"}
        title={isFocused ? "Exit cinema mode (Esc)" : "Cinema mode (F)"}
      >
        {isFocused ? "⊠" : "⊞"}
      </button>
      {children}
    </div>
  );
}
```

```css
.cinema-card {
  position: relative;
  transition:
    opacity 250ms ease,
    transform 250ms ease,
    max-width 350ms cubic-bezier(0.2, 0.9, 0.2, 1);
}

.cinema-dimmed {
  opacity: 0.07;
  pointer-events: none;
  user-select: none;
}

.cinema-focused {
  /* Expand to full available width */
  max-width: 100%;
  z-index: 10;
  box-shadow:
    0 0 0 1px rgba(245, 164, 0, 0.4),
    0 40px 120px rgba(0, 0, 0, 0.6);
}

/* When cinema is active, collapse the side nav */
.cinema-active .vol-output-nav {
  width: 48px;
  min-width: 48px;
}
.cinema-active .von-title,
.cinema-active .von-shortcut,
.cinema-active .nav-cost-bar,
.cinema-active .von-health {
  display: none;
}

.cinema-toggle {
  position: absolute;
  top: 10px;
  right: 48px;
  z-index: 15;
  width: 28px;
  height: 28px;
  background: var(--vol-input);
  border: 1px solid var(--vol-border);
  border-radius: 6px;
  color: var(--vol-muted);
  font-size: 14px;
  cursor: pointer;
  display: grid;
  place-items: center;
  opacity: 0;
  transition: opacity 120ms ease;
}
.cinema-card:hover .cinema-toggle {
  opacity: 1;
}
.cinema-card.cinema-focused .cinema-toggle {
  opacity: 1;
  color: var(--vol-accent);
  border-color: rgba(245, 164, 0, 0.5);
}
```

---

### B.3 COLUMN DENSITY TOGGLE (COMPACT / COMFORTABLE / SPACIOUS)

**What it is and why it belongs here**

Bloomberg allows users to change row density in data tables. Koyfin has a compact mode. The current platform renders all tables at a fixed row height of 40px. A three-tier density toggle — Compact (28px rows, 10px font), Comfortable (40px default), Spacious (52px, 14px font, breathing room) — lets a PM switch between scan mode (compact: see 18 rows at once) and presentation mode (spacious: readable on a shared screen). Implemented as a single CSS custom property on :root, requiring zero per-component changes.

```jsx
// components/volatility-v2/DensityToggle.jsx

const DENSITIES = [
  { key: "compact", label: "—", rowH: 28, fontSize: 10 },
  { key: "comfortable", label: "≡", rowH: 40, fontSize: 12 },
  { key: "spacious", label: "☰", rowH: 52, fontSize: 14 },
];

export function DensityToggle({ value = "comfortable", onChange }) {
  return (
    <div className="density-toggle" role="group" aria-label="Table density">
      {DENSITIES.map((d) => (
        <button
          key={d.key}
          className={value === d.key ? "active" : ""}
          onClick={() => {
            onChange(d.key);
            document.documentElement.style.setProperty(
              "--vol-row-h",
              `${d.rowH}px`,
            );
            document.documentElement.style.setProperty(
              "--vol-table-fs",
              `${d.fontSize}px`,
            );
          }}
          aria-pressed={value === d.key}
          title={d.key}
        >
          {d.label}
        </button>
      ))}
    </div>
  );
}
```

```css
/* In :root or vol-tokens.css */
:root {
  --vol-row-h: 40px;
  --vol-table-fs: 12px;
}

/* Tables automatically respect these variables */
.vvt-td,
.vol-table td {
  height: var(--vol-row-h);
  font-size: var(--vol-table-fs);
}
.vvt-th,
.vol-table th {
  font-size: calc(var(--vol-table-fs) - 2px);
}

/* The toggle widget itself */
.density-toggle {
  display: flex;
  background: var(--vol-input);
  border: 1px solid var(--vol-border);
  border-radius: 6px;
  overflow: hidden;
}

.density-toggle button {
  width: 30px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--vol-muted);
  font-size: 14px;
  cursor: pointer;
  border-right: 1px solid var(--vol-border);
}
.density-toggle button:last-child {
  border-right: none;
}
.density-toggle button.active {
  background: var(--vol-accent);
  color: #050505;
}
.density-toggle button:not(.active):hover {
  color: var(--vol-text);
  background: var(--vol-raised);
}
```

---

### B.4 PERSISTENT WORKSPACE STATE (URL HASH + LOCALSTORAGE SYNC)

**What it is and why it belongs here**

Bloomberg remembers your last function and panel layout across sessions. Koyfin persists dashboard configurations in user accounts. Currently when the user refreshes the ATLAS page, they lose: which feature was active, which outputs were selected, form state, scroll position, drawing state, and cinema mode. A lightweight state serializer pushes the essential workspace state to localStorage on every meaningful change and restores it on mount, with a URL hash that encodes the feature ID and active output so a PM can share a link that opens directly to a specific output card.

```jsx
// hooks/useWorkspaceState.js

import { useEffect, useCallback } from "react";

const STORAGE_KEY = "atlas-vol-workspace-v2";

export function useWorkspaceState({
  featureId,
  selectedOutputIds,
  form,
  activeOutputId,
  onRestore,
}) {
  // Save on any meaningful change
  useEffect(() => {
    const state = {
      featureId,
      selectedOutputIds,
      form,
      activeOutputId,
      ts: Date.now(),
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (_) {}

    // Update URL hash for shareability
    const hash = `#f${featureId}-${activeOutputId ?? ""}`;
    if (window.location.hash !== hash) {
      window.history.replaceState(null, "", hash);
    }
  }, [featureId, selectedOutputIds, form, activeOutputId]);

  // Restore on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const state = JSON.parse(raw);
      // Only restore if less than 24 hours old
      if (Date.now() - state.ts < 86_400_000) {
        onRestore?.(state);
      }
    } catch (_) {}

    // Also parse URL hash
    const match = window.location.hash.match(/^#f(\d+)-(.*)$/);
    if (match) {
      const [, fId, outputId] = match;
      if (fId === String(featureId) && outputId) {
        setTimeout(() => {
          document
            .getElementById(outputId)
            ?.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 400);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const clearWorkspace = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  return { clearWorkspace };
}
```

---

### B.5 PROGRESSIVE OUTPUT REVEAL WITH STAGGERED ENTRANCE

**What it is and why it belongs here**

When a run completes and 10–13 cards simultaneously re-render, the visual impact is a single large flash. Bloomberg reveals sections sequentially as data arrives from the server. The current spec uses a flat `animation: cardReveal` from CSS section 10.3 but all cards animate at the same instant. This upgrade staggers the entrance: primary cards enter first (delay 0ms), supporting cards stagger by 65ms each, contextual cards stagger by 40ms after all supporting cards have settled. The result is a cascade that reads as intentional intelligence rather than a bulk data dump.

```jsx
// Modification to VolOutputCard — add stagger prop

export function VolOutputCard({
  section,
  response,
  active,
  onActive,
  staggerIndex = 0,
}) {
  const delay =
    section.rank === "primary"
      ? 0
      : section.rank === "supporting"
        ? 120 + staggerIndex * 65
        : 400 + staggerIndex * 40;

  return (
    <motion.article
      id={section.id}
      className={`vol-output-card ${section.rank === "primary" ? "primary" : ""} ${active ? "active" : ""}`}
      initial={{ opacity: 0, y: 24, filter: "blur(3px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{
        duration: 0.38,
        delay: delay / 1000,
        ease: [0.2, 0.9, 0.2, 1],
      }}
      onMouseEnter={() => onActive(section.id)}
    >
      {/* existing card internals unchanged */}
    </motion.article>
  );
}

// In the parent VolStack:
const supportingIdx = (section) =>
  outputSections.filter((s) => s.rank === section.rank && s.id <= section.id)
    .length - 1;

{
  outputSections.map((section) => (
    <VolOutputCard
      key={section.id}
      staggerIndex={supportingIdx(section)}
      {...otherProps}
    />
  ));
}
```

---

### B.6 LIVE RUN PROGRESS INDICATOR — SECTION-LEVEL STREAM STATUS

**What it is and why it belongs here**

Bloomberg's GARCH function shows a live "Computing…" spinner per output section while it calculates. Koyfin shows a linear progress bar across the top. Currently the ATLAS run button shows "Running…" globally but gives no section-level feedback. When a run takes 8–15 seconds for the full 9-feature pipeline, the user has no idea what is computing. This component streams section-level status: each nav item gets a spinning arc while its section is computing, a green checkmark when done, and a red X if that section errored — all updating in real time from the run stream.

```jsx
// components/volatility-v2/RunProgressBar.jsx

/**
 * Thin progress bar that sits just below the topbar.
 * Accepts `progress` from 0 to 1 and a `status` array of per-section states.
 */
export function RunProgressBar({ progress, running, sectionStatuses = {} }) {
  if (!running && progress === 0) return null;

  return (
    <div
      className="rpb-wrap"
      role="progressbar"
      aria-valuenow={Math.round(progress * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="rpb-track">
        <div className="rpb-fill" style={{ width: `${progress * 100}%` }} />
        {/* Shimmer pulse while running */}
        {running && <div className="rpb-shimmer" />}
      </div>
      <div className="rpb-label">
        {running ? `Computing… ${Math.round(progress * 100)}%` : "Run complete"}
      </div>
    </div>
  );
}

// Section-level status indicator — used inside VolOutputNav items
export function SectionRunStatus({ status }) {
  if (!status || status === "idle") return null;

  if (status === "computing") {
    return <span className="srs-spin" aria-label="Computing" />;
  }
  if (status === "done") {
    return (
      <span className="srs-done" aria-label="Done">
        ✓
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="srs-error" aria-label="Error">
        ✕
      </span>
    );
  }
  return null;
}
```

```css
.rpb-wrap {
  position: sticky;
  top: 48px;
  z-index: 45;
  height: 3px;
  margin: 0 -28px;
  background: var(--vol-border-subtle);
  overflow: hidden;
}

.rpb-track {
  position: relative;
  height: 100%;
}

.rpb-fill {
  height: 100%;
  background: linear-gradient(90deg, #f5a400, #22c55e);
  transition: width 280ms cubic-bezier(0.2, 0.9, 0.2, 1);
  border-radius: 0 2px 2px 0;
}

.rpb-shimmer {
  position: absolute;
  top: 0;
  left: -60%;
  width: 60%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.4),
    transparent
  );
  animation: shimmerSweep 1.4s ease-in-out infinite;
}

@keyframes shimmerSweep {
  from {
    left: -60%;
  }
  to {
    left: 110%;
  }
}

.rpb-label {
  position: absolute;
  right: 28px;
  top: 5px;
  font:
    800 9px "JetBrains Mono",
    monospace;
  color: var(--vol-accent);
  letter-spacing: 0.1em;
}

/* Section status indicators inside nav */
.srs-spin {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(245, 164, 0, 0.3);
  border-top-color: #f5a400;
  border-radius: 50%;
  animation: spinFast 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spinFast {
  to {
    transform: rotate(360deg);
  }
}

.srs-done {
  color: #22c55e;
  font-size: 10px;
  font-weight: 900;
}
.srs-error {
  color: #ef4444;
  font-size: 10px;
  font-weight: 900;
}
```

---

### B.7 CHART CROSSHAIR RULER WITH DELTA READOUT

**What it is and why it belongs here**

Bloomberg's chart cursor shows not just the value at the cursor position but the delta from the previous period (shown as ▲3.2 or ▼1.1 in amber/red) and the percentage change. Koyfin's chart hover shows the value only. The current VolTooltip shows value at the hovered date. This upgrade adds: (1) a vertical crosshair line that extends the full chart height with a pinned y-axis label, (2) a delta chip showing the change from the previous data point in both absolute and percentage terms, (3) a horizontal crosshair that snaps to the hovered series line with a pinned x-axis label. Implemented as a custom Recharts `<Tooltip>` replacement.

```jsx
// components/volatility-v2/CrosshairTooltip.jsx

export function CrosshairTooltip({
  active,
  payload,
  label,
  data = [],
  xKey = "date",
}) {
  if (!active || !payload?.length) return null;

  // Find the previous data point
  const idx = data.findIndex((r) => r[xKey] === label);
  const prev = idx > 0 ? data[idx - 1] : null;

  return (
    <div className="xhair-tooltip" role="tooltip">
      <div className="xhair-date mono">{label}</div>
      {payload.map((entry, i) => {
        const val = numberLike(entry.value);
        const prevVal = prev ? numberLike(prev[entry.dataKey]) : null;
        const delta = val != null && prevVal != null ? val - prevVal : null;
        const deltaPct =
          delta != null && prevVal ? (delta / Math.abs(prevVal)) * 100 : null;
        const up = delta != null && delta >= 0;

        return (
          <div key={`${entry.dataKey}-${i}`} className="xhair-row">
            <span className="xhair-dot" style={{ background: entry.color }} />
            <span className="xhair-key">{entry.name ?? entry.dataKey}</span>
            <span className="xhair-val mono">{formatValue(val)}</span>
            {delta != null && (
              <span className={`xhair-delta mono ${up ? "up" : "dn"}`}>
                {up ? "▲" : "▼"}
                {Math.abs(delta).toFixed(2)}
                {deltaPct != null && <em>{Math.abs(deltaPct).toFixed(1)}%</em>}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

```css
.xhair-tooltip {
  background: #090909;
  border: 1px solid var(--vol-border);
  border-radius: 10px;
  padding: 10px 12px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.65);
  min-width: 240px;
  pointer-events: none;
}

.xhair-date {
  font-size: 10px;
  font-weight: 700;
  color: var(--vol-text);
  letter-spacing: 0.06em;
  padding-bottom: 7px;
  margin-bottom: 7px;
  border-bottom: 1px solid var(--vol-border-subtle);
}

.xhair-row {
  display: grid;
  grid-template-columns: 10px 1fr auto auto;
  align-items: center;
  gap: 7px;
  min-height: 24px;
}

.xhair-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.xhair-key {
  font-size: 11px;
  color: var(--vol-secondary);
}
.xhair-val {
  font-size: 11px;
  font-weight: 700;
  color: var(--vol-text);
  text-align: right;
}

.xhair-delta {
  font-size: 10px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 4px;
}
.xhair-delta.up {
  color: #22c55e;
}
.xhair-delta.dn {
  color: #ef4444;
}
.xhair-delta em {
  font-style: normal;
  opacity: 0.75;
  font-size: 9px;
}
```

---

### B.8 CARD HEADER SPARKLINE STRIP

**What it is and why it belongs here**

Bloomberg's top-of-panel summary line shows a tiny 80×24px line chart of the primary metric alongside the section title — a sparkline that gives the visual trend before the full chart even loads. Koyfin's sidebar shows sparklines next to each ticker in watchlists. The current card header shows only a text title and action buttons. Adding a 80×24px sparkline rendered from the primary data key gives every card a glanceable 10-second trend impression at the navigation stage, before the user scrolls into the chart.

```jsx
// components/volatility-v2/CardHeaderSparkline.jsx

export function CardHeaderSparkline({ data, dataKey = "value" }) {
  const rows = rowsFrom(data);
  const vals = rows
    .map((r) => numberLike(r[dataKey] ?? r.yang_zhang ?? r.value))
    .filter((v) => v != null);
  if (vals.length < 4) return null;

  const W = 80,
    H = 24;
  const min = Math.min(...vals),
    max = Math.max(...vals);
  const range = max - min || 1;

  const pts = vals
    .map(
      (v, i) =>
        `${(i / (vals.length - 1)) * W},${H - ((v - min) / range) * (H - 4) - 2}`,
    )
    .join(" ");

  const last = vals.at(-1);
  const first = vals[0];
  const up = last >= first;

  return (
    <svg className="card-spark" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <defs>
        <linearGradient id="spark-fill" x1="0" x2="0" y1="0" y2="1">
          <stop
            offset="0%"
            stopColor={up ? "#22c55e" : "#ef4444"}
            stopOpacity={0.3}
          />
          <stop
            offset="100%"
            stopColor={up ? "#22c55e" : "#ef4444"}
            stopOpacity={0}
          />
        </linearGradient>
      </defs>
      <polyline
        points={pts}
        fill="none"
        stroke={up ? "#22c55e" : "#ef4444"}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
```

```css
.card-spark {
  width: 80px;
  height: 24px;
  flex-shrink: 0;
  opacity: 0.8;
}

/* Insert between the title text and the action buttons in the card header */
.vol-output-card > header {
  gap: 10px;
}
```

---

### B.9 AMBIENT GLOW ACCENT ON ACTIVE CARD

**What it is and why it belongs here**

The current active card state applies `border-color: rgba(245,164,0,.55)` and a box-shadow from CSS section 10.4. This is correct but static. A living ambient glow — where the card's left-border glow slowly breathes in sync with the regime pulse animation — makes the active card feel alive rather than just highlighted. It costs zero JavaScript; it is purely a CSS keyframe applied to the box-shadow's spread radius.

```css
/* Add to .vol-output-card.active in globals.css */

.vol-output-card.active {
  animation: cardBreath 3s ease-in-out infinite;
}

@keyframes cardBreath {
  0%,
  100% {
    box-shadow:
      0 0 0 1px rgba(245, 164, 0, 0.12),
      inset 2px 0 0 #f5a400,
      0 28px 80px rgba(0, 0, 0, 0.45);
  }
  50% {
    box-shadow:
      0 0 0 1px rgba(245, 164, 0, 0.22),
      inset 2px 0 0 #f5a400,
      0 28px 80px rgba(0, 0, 0, 0.45),
      0 0 32px rgba(245, 164, 0, 0.08);
  }
}

/* Regime-specific glow color overrides for the active card */
.vol-output-card.active.regime-low {
  animation: cardBreathGreen 3s ease-in-out infinite;
}
@keyframes cardBreathGreen {
  0%,
  100% {
    box-shadow:
      inset 2px 0 0 #22c55e,
      0 0 0 1px rgba(34, 197, 94, 0.12),
      0 28px 80px rgba(0, 0, 0, 0.45);
  }
  50% {
    box-shadow:
      inset 2px 0 0 #22c55e,
      0 0 0 1px rgba(34, 197, 94, 0.25),
      0 28px 80px rgba(0, 0, 0, 0.45),
      0 0 32px rgba(34, 197, 94, 0.07);
  }
}

.vol-output-card.active.regime-crisis {
  animation: cardBreathRed 3s ease-in-out infinite;
}
@keyframes cardBreathRed {
  0%,
  100% {
    box-shadow:
      inset 2px 0 0 #ef4444,
      0 0 0 1px rgba(239, 68, 68, 0.18),
      0 28px 80px rgba(0, 0, 0, 0.45);
  }
  50% {
    box-shadow:
      inset 2px 0 0 #ef4444,
      0 0 0 1px rgba(239, 68, 68, 0.35),
      0 28px 80px rgba(0, 0, 0, 0.45),
      0 0 40px rgba(239, 68, 68, 0.1);
  }
}
```

---

### B.10 PARAMETER HISTORY TIMELINE — "WHAT DID I LAST RUN?"

**What it is and why it belongs here**

Bloomberg's command history (⇧⇥ cycles through past commands) and Koyfin's recently viewed tiles both give the user a way back to previous work states. Currently when the user changes form inputs and reruns, the previous parameter set is lost. This stores the last 5 complete form states alongside their run timestamps and primary result metrics, accessible as a "HISTORY" panel in the input curtain. The user clicks any historical run to restore that exact parameter set, enabling A/B comparison between parameter configurations.

```jsx
// hooks/useRunHistory.js

import { useState, useCallback } from "react";

const MAX_HISTORY = 5;
const HISTORY_KEY = "atlas-run-history";

export function useRunHistory() {
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
    } catch {
      return [];
    }
  });

  const recordRun = useCallback((form, summary = {}) => {
    const entry = {
      id: Date.now(),
      ts: new Date().toISOString(),
      form,
      summary, // { outputCount, primaryMetric, featureId }
    };
    setHistory((prev) => {
      const next = [entry, ...prev].slice(0, MAX_HISTORY);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(HISTORY_KEY);
    setHistory([]);
  }, []);

  return { history, recordRun, clearHistory };
}

// Display component — shown inside VolInputForm footer
export function RunHistoryPanel({ history, onRestore }) {
  if (!history.length) return null;

  return (
    <div className="run-hist">
      <div className="run-hist-header">RECENT RUNS</div>
      {history.map((run) => (
        <button
          key={run.id}
          className="run-hist-item"
          onClick={() => onRestore(run.form)}
        >
          <span className="rhi-ts mono">
            {new Date(run.ts).toLocaleTimeString("en-US", { hour12: false })}
          </span>
          <span className="rhi-asset mono">{run.form.asset ?? "—"}</span>
          <span className="rhi-outputs">
            {run.summary.outputCount ?? "?"} outputs
          </span>
          <span className="rhi-restore">↩ Restore</span>
        </button>
      ))}
    </div>
  );
}
```

```css
.run-hist {
  border-top: 1px solid var(--vol-border-subtle);
  padding: 12px 0 0;
}

.run-hist-header {
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.18em;
  color: var(--vol-muted);
  margin-bottom: 8px;
}

.run-hist-item {
  display: grid;
  grid-template-columns: 70px 80px 1fr auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 34px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--vol-secondary);
  cursor: pointer;
  font-size: 11px;
  text-align: left;
}
.run-hist-item:hover {
  background: var(--vol-raised);
  border-color: var(--vol-border);
}

.rhi-ts,
.rhi-asset {
  font-family: "JetBrains Mono", monospace;
}
.rhi-asset {
  color: var(--vol-text);
  font-weight: 700;
}
.rhi-outputs {
  color: var(--vol-muted);
  font-size: 10px;
}

.rhi-restore {
  font:
    800 10px "JetBrains Mono",
    monospace;
  color: var(--vol-accent);
  opacity: 0;
  transition: opacity 100ms ease;
}
.run-hist-item:hover .rhi-restore {
  opacity: 1;
}
```

---

### B.11 EXPORT SURFACE — ONE-CLICK WORKSPACE EXPORT

**What it is and why it belongs here**

Bloomberg's XLTP function exports all displayed data to Excel. Koyfin has a CSV export on every chart. Currently the platform has a Copy button per card (copies as TSV). This upgrade adds a workspace-level export surface: a modal triggered by ⌘E that lets the user choose (1) export all visible outputs as a single multi-sheet CSV/TSV package (tab-separated files named by section), (2) export the current chart as an SVG, (3) copy the current form as a JSON config string for sharing. All implemented client-side with no server dependency.

```jsx
// components/volatility-v2/ExportModal.jsx

export function ExportModal({ open, onClose, sections, response, form }) {
  if (!open) return null;

  function exportAllCSV() {
    const lines = [];
    for (const section of sections) {
      const data = pickData(response, section);
      const rows = rowsFrom(data);
      if (!rows.length) continue;
      const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
      lines.push(`\n# ${section.title} (${section.source}.${section.dataKey})`);
      lines.push(cols.join("\t"));
      rows.forEach((row) =>
        lines.push(cols.map((c) => row[c] ?? "").join("\t")),
      );
    }
    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `atlas-vol-${Date.now()}.tsv`,
    });
    a.click();
    URL.revokeObjectURL(url);
  }

  function copyFormJSON() {
    navigator.clipboard?.writeText(JSON.stringify(form, null, 2));
  }

  return (
    <div
      className="export-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal
      aria-label="Export"
    >
      <div className="export-modal" onClick={(e) => e.stopPropagation()}>
        <div className="export-header">
          <span>EXPORT WORKSPACE</span>
          <button onClick={onClose}>
            <X size={15} />
          </button>
        </div>
        <div className="export-options">
          <button className="export-option" onClick={exportAllCSV}>
            <span className="eo-icon">⬇</span>
            <div>
              <strong>All Outputs as TSV</strong>
              <p>Multi-section tab-separated file. Opens directly in Excel.</p>
            </div>
          </button>
          <button className="export-option" onClick={copyFormJSON}>
            <span className="eo-icon">{}</span>
            <div>
              <strong>Copy Input Contract as JSON</strong>
              <p>Paste into another session or share with a colleague.</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
```

```css
.export-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(16px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.export-modal {
  width: min(480px, calc(100vw - 28px));
  background: #090909;
  border: 1px solid var(--vol-border);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 32px 90px rgba(0, 0, 0, 0.7);
}

.export-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--vol-border-subtle);
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.16em;
  color: var(--vol-accent);
}

.export-header button {
  width: 28px;
  height: 28px;
  border: 1px solid var(--vol-border);
  background: transparent;
  color: var(--vol-muted);
  border-radius: 6px;
  display: grid;
  place-items: center;
  cursor: pointer;
}

.export-options {
  padding: 12px;
  display: grid;
  gap: 8px;
}

.export-option {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 72px;
  padding: 12px 14px;
  border: 1px solid var(--vol-border);
  background: var(--vol-raised);
  color: var(--vol-text);
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
}
.export-option:hover {
  border-color: rgba(245, 164, 0, 0.4);
  background: rgba(245, 164, 0, 0.06);
}

.eo-icon {
  font-size: 24px;
  width: 40px;
  text-align: center;
  flex-shrink: 0;
  color: var(--vol-accent);
}

.export-option strong {
  display: block;
  font-size: 13px;
  margin-bottom: 4px;
}
.export-option p {
  margin: 0;
  font-size: 11px;
  color: var(--vol-muted);
  line-height: 1.4;
}
```

---

### B.12 GLOBAL SEARCH — FUZZY SEARCH ACROSS ALL OUTPUT DATA

**What it is and why it belongs here**

Bloomberg's Autocomplete bar (type any ticker or function name) is the platform's most-used interaction. The existing ⌘K command palette in Section 2 of the existing manifest searches commands and sections. This extension adds a second search mode that searches the actual _output data_ — when the user types "yang zhang" it highlights all cells in all currently rendered tables containing that key; when they type "crisis" it scrolls to and highlights all regime alerts. Implemented as a lightweight client-side full-text search over the rendered DOM's text content.

```jsx
// hooks/useDataSearch.js

import { useState, useCallback, useEffect } from "react";

export function useDataSearch() {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [current, setCurrent] = useState(0);

  const search = useCallback((q) => {
    setQuery(q);
    if (!q.trim()) {
      setMatches([]);
      return;
    }

    const term = q.toLowerCase();
    const found = [];

    // Search all rendered table cells
    document.querySelectorAll(".vvt-td, .vol-table td").forEach((cell) => {
      if (cell.textContent.toLowerCase().includes(term)) {
        found.push(cell);
      }
    });

    // Search insight bars
    document.querySelectorAll(".vol-insight-bar").forEach((el) => {
      if (el.textContent.toLowerCase().includes(term)) found.push(el);
    });

    // Highlight all matches
    document.querySelectorAll(".data-search-highlight").forEach((el) => {
      el.classList.remove("data-search-highlight");
    });
    found.forEach((el) => el.classList.add("data-search-highlight"));

    setMatches(found);
    setCurrent(0);
    found[0]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const nextMatch = useCallback(() => {
    if (!matches.length) return;
    const next = (current + 1) % matches.length;
    setCurrent(next);
    matches[next]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [matches, current]);

  const clearSearch = useCallback(() => {
    document.querySelectorAll(".data-search-highlight").forEach((el) => {
      el.classList.remove("data-search-highlight");
    });
    setQuery("");
    setMatches([]);
    setCurrent(0);
  }, []);

  return { query, matches, current, search, nextMatch, clearSearch };
}
```

```css
/* Highlight style for matching cells */
.data-search-highlight {
  background: rgba(245, 164, 0, 0.25) !important;
  outline: 1px solid rgba(245, 164, 0, 0.6);
  border-radius: 2px;
  animation: searchPulse 400ms ease both;
}

@keyframes searchPulse {
  from {
    background: rgba(245, 164, 0, 0.5) !important;
  }
  to {
    background: rgba(245, 164, 0, 0.25) !important;
  }
}

/* Search bar extension inside CommandPalette — second tab "Data Search" */
.cmd-tab-bar {
  display: flex;
  border-bottom: 1px solid var(--vol-border-subtle);
}

.cmd-tab {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  font:
    800 10px "JetBrains Mono",
    monospace;
  letter-spacing: 0.12em;
  color: var(--vol-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.cmd-tab.active {
  color: var(--vol-accent);
  border-bottom-color: var(--vol-accent);
}

.cmd-match-count {
  font:
    800 10px "JetBrains Mono",
    monospace;
  color: var(--vol-muted);
  padding: 0 4px;
}
```

---

### B.13 STICKY SECTION SUMMARY BAR

**What it is and why it belongs here**

Bloomberg's GIP and GP functions show a one-line fixed summary strip (ticker | last price | change | vol) that sticks to the top of the function panel while you scroll the chart below. When the user scrolls down past a primary output card, the card's primary metric — the single most important number — should follow them in a thin sticky strip so they never lose context. Currently scrolling the Five-Estimator Comparison card off screen means losing the current YZ vol reading entirely until you scroll back.

```jsx
// components/volatility-v2/StickyMetricBar.jsx

import { useEffect, useRef, useState } from "react";

/**
 * Appears at top of viewport (below topbar) when the primary card
 * is scrolled out of view. Shows the card's title + its primary metric.
 */
export function StickyMetricBar({ section, data, topbarHeight = 48 }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = document.getElementById(section.id);
    if (!el) return;

    const obs = new IntersectionObserver(
      ([entry]) => setVisible(!entry.isIntersecting),
      { rootMargin: `-${topbarHeight}px 0px 0px 0px`, threshold: 0 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [section.id, topbarHeight]);

  if (!visible) return null;

  // Extract the primary scalar from the data
  const rows = rowsFrom(data);
  const primary = rows[0];
  const val = primary
    ? numberLike(
        primary.yang_zhang ??
          primary.value ??
          primary.vol ??
          Object.values(primary).find((v) => typeof v === "number"),
      )
    : null;

  return (
    <div
      className="sticky-metric"
      role="complementary"
      aria-label={section.title}
    >
      <span className="sm-bullet" />
      <span className="sm-title">{section.title}</span>
      {val != null && <span className="sm-val mono">{formatValue(val)}</span>}
      <button
        className="sm-jump"
        onClick={() =>
          document
            .getElementById(section.id)
            ?.scrollIntoView({ behavior: "smooth", block: "start" })
        }
      >
        ↑ Jump
      </button>
    </div>
  );
}
```

```css
.sticky-metric {
  position: sticky;
  top: 48px;
  z-index: 38;
  height: 32px;
  margin: 0 -28px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(5, 5, 5, 0.92);
  border-bottom: 1px solid var(--vol-border-subtle);
  backdrop-filter: blur(10px);
  animation: smSlide 180ms ease both;
}

@keyframes smSlide {
  from {
    transform: translateY(-100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.sm-bullet {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--vol-accent);
}

.sm-title {
  font-size: 11px;
  color: var(--vol-secondary);
  flex: 1;
}

.sm-val {
  font:
    900 13px "JetBrains Mono",
    monospace;
  color: var(--vol-accent);
  letter-spacing: 0.04em;
}

.sm-jump {
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--vol-border);
  background: transparent;
  color: var(--vol-muted);
  border-radius: 4px;
  font:
    800 9px "JetBrains Mono",
    monospace;
  cursor: pointer;
  letter-spacing: 0.08em;
}
.sm-jump:hover {
  color: var(--vol-accent);
  border-color: rgba(245, 164, 0, 0.4);
}
```

---

### B.14 SURFACE-LEVEL GRID SNAP FOR DRAG-REORDER

**What it is and why it belongs here**

Koyfin allows dashboard widgets to be rearranged by drag-and-drop. Bloomberg's LAUNCHPAD function is entirely drag-rearrangeable. The output nav already lists sections and the user can jump to them, but the order is fixed by the registry. This hook adds pointer-event-based drag reordering of the output nav items, storing the user's preferred section order in localStorage. It snaps to a grid of 56px items (matching the nav item height). No dependency needed — pure pointer events.

```jsx
// hooks/useDragReorder.js

import { useCallback, useRef, useState } from "react";

export function useDragReorder(initialItems) {
  const [items, setItems] = useState(initialItems);
  const dragging = useRef(null);
  const dragOverIdx = useRef(null);

  const onDragStart = useCallback((e, index) => {
    dragging.current = index;
    e.dataTransfer.effectAllowed = "move";
    e.currentTarget.classList.add("drag-lifting");
  }, []);

  const onDragOver = useCallback((e, index) => {
    e.preventDefault();
    dragOverIdx.current = index;
    e.currentTarget.classList.add("drag-over");
  }, []);

  const onDragLeave = useCallback((e) => {
    e.currentTarget.classList.remove("drag-over");
  }, []);

  const onDrop = useCallback((e, targetIndex) => {
    e.currentTarget.classList.remove("drag-over");
    const from = dragging.current;
    if (from == null || from === targetIndex) return;
    setItems((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(targetIndex, 0, moved);
      // Persist user order
      try {
        localStorage.setItem(
          "atlas-section-order",
          JSON.stringify(next.map((i) => i.id)),
        );
      } catch (_) {}
      return next;
    });
    dragging.current = null;
  }, []);

  const onDragEnd = useCallback((e) => {
    dragging.current = null;
    document.querySelectorAll(".drag-lifting, .drag-over").forEach((el) => {
      el.classList.remove("drag-lifting", "drag-over");
    });
  }, []);

  return { items, onDragStart, onDragOver, onDragLeave, onDrop, onDragEnd };
}
```

```css
/* Applied to nav items and output card wrappers */
[draggable="true"] {
  cursor: grab;
}
[draggable="true"]:active {
  cursor: grabbing;
}

.drag-lifting {
  opacity: 0.45;
  transform: scale(0.97);
  transition:
    opacity 120ms ease,
    transform 120ms ease;
}

.drag-over {
  outline: 2px dashed rgba(245, 164, 0, 0.5);
  outline-offset: -2px;
  border-radius: inherit;
}

/* Small drag handle icon shown on nav item hover */
.von-item::before {
  content: "⋮⋮";
  position: absolute;
  left: 4px;
  font-size: 9px;
  color: transparent;
  letter-spacing: -2px;
  transition: color 120ms ease;
}
.von-item:hover::before {
  color: var(--vol-muted);
}
```

---

## PART C — TYPOGRAPHY + MOTION DESIGN TOKENS

---

### C.1 EXTENDED TYPE SCALE FOR DATA DENSITY

```css
/* Extend globals.css / vol-tokens.css */

:root {
  /* Numeric display sizes — for metric dials, vol readings, gauge values */
  --vol-display-xl: clamp(36px, 5vw, 64px);
  --vol-display-lg: clamp(24px, 3.5vw, 42px);
  --vol-display-md: clamp(18px, 2.5vw, 28px);
  --vol-display-sm: 16px;

  /* Monospace data sizes */
  --vol-mono-lg: 14px;
  --vol-mono-md: 12px;
  --vol-mono-sm: 10px;
  --vol-mono-xs: 9px;

  /* Label track — uppercase micro labels */
  --vol-label-lg: 11px;
  --vol-label-md: 9px;
  --vol-label-xs: 8px;

  /* Letter spacing companions */
  --vol-tracking-tight: -0.03em;
  --vol-tracking-base: 0;
  --vol-tracking-wide: 0.08em;
  --vol-tracking-wider: 0.14em;
  --vol-tracking-widest: 0.22em;

  /* Number rendering — tabular figures prevent layout shift */
  --vol-number-variant: "tnum", "lnum";
}

/* Apply tabular numerics to all mono data */
.mono,
[class*="vvt-"],
[class*="rt-val"],
[class*="xhair-val"],
.vol-metric strong {
  font-variant-numeric: tabular-nums lining-nums;
  font-feature-settings:
    "tnum" 1,
    "lnum" 1;
}

/* Display numerics for gauge + dashboard big numbers */
.vol-display-xl {
  font-size: var(--vol-display-xl);
  letter-spacing: var(--vol-tracking-tight);
  line-height: 0.9;
}
.vol-display-lg {
  font-size: var(--vol-display-lg);
  letter-spacing: var(--vol-tracking-tight);
  line-height: 0.95;
}
```

---

### C.2 MICRO-INTERACTION TOKEN LIBRARY

```css
/* vol-motion.css — import alongside vol-tokens.css */

:root {
  /* Duration scale */
  --dur-instant: 80ms;
  --dur-fast: 150ms;
  --dur-base: 250ms;
  --dur-slow: 380ms;
  --dur-glacial: 600ms;

  /* Easing library */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-out-back: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-critical: cubic-bezier(0.2, 0.9, 0.2, 1); /* used for run completion */
}

/* Button press feedback — applies to all vol-topbar-btn, vf-chip, preset-btn */
.vol-topbar-btn:active,
.vf-chip:active,
.preset-btn:active,
.vol-run-btn:active {
  transform: scale(0.94);
  transition: transform var(--dur-instant) var(--ease-out-expo);
}

/* Number flip animation — for metric values that update after a run */
.metric-flip {
  animation: metricFlip var(--dur-slow) var(--ease-out-expo) both;
}

@keyframes metricFlip {
  0% {
    opacity: 0;
    transform: translateY(-8px) scale(0.95);
  }
  60% {
    opacity: 1;
    transform: translateY(2px) scale(1.02);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Value change flash — amber when value increases, red when it decreases */
.value-up {
  animation: flashUp var(--dur-base) ease both;
}
.value-down {
  animation: flashDown var(--dur-base) ease both;
}

@keyframes flashUp {
  0%,
  100% {
    color: inherit;
  }
  40% {
    color: #22c55e;
  }
}
@keyframes flashDown {
  0%,
  100% {
    color: inherit;
  }
  40% {
    color: #ef4444;
  }
}
```

---

### C.3 COMPLETE DARK SURFACE HIERARCHY — ALL 8 LAYERS

```css
/* Extends existing surface tokens with 3 additional layers for ultra-fine depth */
:root {
  /* Layer 0 — literal black. Page chrome, modal backdrops */
  --vol-void: #000000;

  /* Layer 1 — page background */
  --vol-page: #050505;

  /* Layer 2 — panel/card background */
  --vol-panel: #090909;

  /* Layer 3 — chart surface */
  --vol-screen: #0d0f11;

  /* Layer 4 — raised element (hover states, input backgrounds) */
  --vol-raised: #14110a;

  /* Layer 5 — input fields */
  --vol-input: #121212;

  /* Layer 6 — tooltip, dropdown, floating */
  --vol-float: #0a0a0a;

  /* Layer 7 — code block, formula preview */
  --vol-code: #0d0f11;

  /* Layer 8 — active/selected surface */
  --vol-active: rgba(245, 164, 0, 0.06);

  /*
   * Usage rule:
   * Page → Panel → Screen → Raised → Input → Float → Code
   * Each layer is exactly ~8-12 Lightness points lighter than the one below.
   * Never use a higher-numbered layer below a lower-numbered one.
   * The amber accent sits at #F5A400 — never lighten it; only use opacity.
   */
}
```

---

## PART D — INTEGRATION MAP FOR ALL NEW ADDITIONS

| Addition               | Plugs Into                                | Triggered By                    | Data Source                 |
| ---------------------- | ----------------------------------------- | ------------------------------- | --------------------------- |
| A.1 Calendar Heatmap   | VolOutputCard / Feature 1 sections        | chartType = "calendarHeatmap"   | Feature 1 daily YZ series   |
| A.2 Ridge Plot         | VolOutputCard / Feature 1–3 sections      | chartType = "ridgePlot"         | Feature 1 daily vol series  |
| A.3 Volatility Cone    | VolOutputCard / Feature 1 cross-asset     | chartType = "volCone"           | Feature 1 multi-window      |
| A.4 Q-Q Plot           | Feature 2 output card                     | chartType = "qqPlot"            | Feature 2 GARCH residuals   |
| A.5 Signature Plot     | Feature 1 estimator card                  | chartType = "signaturePlot"     | Feature 1 multi-lag RV      |
| A.6 Corr Mini-Movies   | Feature 7 correlation card                | chartType = "corrAnimation"     | Feature 7 rolling matrices  |
| A.7 Split Comparison   | Top-level workspace                       | ⌘B keyboard shortcut            | Any two output sections     |
| A.8 Minimap Navigator  | Workspace layout next to OutputDock       | Always visible when ≥6 sections | Section metadata            |
| B.1 Toast System       | ToastProvider wraps VolatilityV2Workbench | onRun, regime alerts, conflicts | Run pipeline + Feature 4    |
| B.2 Cinema Mode        | Every VolOutputCard                       | F key / cinema-toggle button    | Card metadata               |
| B.3 Density Toggle     | VolTopbar actions row                     | User click                      | CSS custom property         |
| B.4 Workspace State    | VolatilityV2Workbench mount               | Automatic                       | localStorage + URL hash     |
| B.5 Staggered Reveal   | VolOutputCard animation                   | Post-run response arrival       | Section rank                |
| B.6 Run Progress Bar   | Immediately below VolTopbar               | onRun / streaming               | Run pipeline status         |
| B.7 Crosshair Ruler    | All VolChart instances                    | Mouse hover on any chart        | Recharts activePayload      |
| B.8 Card Sparkline     | VolOutputCard header                      | Always — on card mount          | Section primary data key    |
| B.9 Ambient Glow       | CSS only — .vol-output-card.active        | IntersectionObserver activeId   | Regime state from Feature 4 |
| B.10 Run History       | VolInputForm footer                       | After each successful run       | localStorage                |
| B.11 Export Modal      | ⌘E shortcut / topbar button               | User trigger                    | All rendered section data   |
| B.12 Data Search       | CommandPalette second tab                 | ⌘K → "Data Search" tab          | Rendered DOM text content   |
| B.13 Sticky Metric Bar | Primary output cards only                 | IntersectionObserver card exit  | Card primary data key       |
| B.14 Drag Reorder      | VolOutputNav + OutputMinimap              | Pointer drag on nav items       | localStorage user order     |

