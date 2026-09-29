## Implementation Checklist — 2026-06-09

Status is for the Volatility V2 frontend hub/layout work just applied in:

- `frontend/src/app/labs/volatility-v2/page.js`
- `frontend/src/app/labs/volatility-v2/layout.js`
- `frontend/src/components/VolCommandPalette.jsx`
- `frontend/package.json`
- `frontend/package-lock.json`

### Completed

- [x] Installed frontend upgrade dependencies needed for this pass:
  - `framer-motion`
  - `@react-spring/web`
  - `react-plotly.js`
  - `plotly.js-dist-min`
  - `plotly.js`
  - `@visx/heatmap`
  - `@visx/network`
  - `@visx/scale`
  - `@visx/group`
  - `@visx/shape`
  - `@visx/axis`
  - `@visx/gradient`
  - `@visx/responsive`
  - `d3-force`
- [x] Added real `Cmd+K` command palette for Volatility V2.
  - Opens from keyboard.
  - Opens from the bottom dock `⌘K` badge.
  - Navigates to all V01-V09 feature routes.
  - Jumps to cluster anchors on the Volatility home page.
- [x] Replaced the static hero SVG network with an animated canvas particle field.
- [x] Replaced manual `IntersectionObserver` feature-card reveal with `framer-motion`.
- [x] Added staggered bullet reveal inside every Volatility feature card.
- [x] Added Framer scroll-linked ghost numbers to cluster intro sections.
- [x] Replaced stat count-up with a spring-based odometer-style number animation.
- [x] V01 Estimators preview upgraded from generic area chart to a realized-volatility signature plot.
- [x] V02 GARCH preview upgraded to a real interactive Plotly 3D volatility term-structure surface.
- [x] V04 Regimes preview upgraded to a calendar-style regime heatmap.
- [x] V06 Spillover preview upgraded to a force-positioned directed spillover network using `d3-force`.
- [x] V07 DCC preview upgraded to an interactive circle correlation matrix with row/column hover slices.
- [x] V08 Stress preview upgraded to a sequential stress waterfall chart.
- [x] V09 Budget preview upgraded to a bullet-chart style budget-vs-actual surface.
- [x] V01 estimator distribution/violin inset added alongside the signature plot.
- [x] V05 VRP preview upgraded to a scatter/regression chart with confidence band.
- [x] Stripe/Linear-style flashlight effect added to the Volatility feature-card stack.
- [x] Hero background replaced with ambient multi-radial mesh lighting.
- [x] Feature-card border/background upgraded to layered padding-box/border-box treatment.
- [x] Chart panels upgraded to terminal chrome with three window dots, mono path-style labels, and pulsing live indicator.
- [x] Inset top-light highlight added to dark panels/stats surfaces.
- [x] Hero accent headline span upgraded to clipped gold gradient text.
- [x] Tabular/slashed-zero numeric rendering applied to Volatility stats, chart shells, dock pills, live pills, command badge, SVG chart labels, and budget rows.
- [x] Cluster section sequence treatment retained/enhanced with scroll-linked Framer ghost numbers and stack counter reset.
- [x] Removed old dead landing-page reveal observer logic after Framer Motion replacement.
- [x] Removed stale preview datasets no longer used by the upgraded visuals.
- [x] Verified the edited Volatility frontend files with ESLint.
- [x] Verified `/labs/volatility-v2` returns HTTP 200 after fixing the Plotly dependency issue.

### Partially Completed

- [~] “Replace Recharts with the right tool per module.”
  - Done for V01, V02, V04, V05, V06, V07, V08, V09 on the hub previews.
  - V03 HAR still uses Recharts because the spec explicitly said Recharts was acceptable there.
- [~] Visx stack installed.
  - Packages are installed and ready.
  - The current hub implementation uses pure SVG plus `d3-force` for several visuals rather than importing Visx primitives directly, because the pure SVG versions integrate cleanly with the existing page and avoid extra React 19 peer-dependency surface area while preserving the requested output behavior.

### Not Completed Yet

- [ ] True Visx `HeatmapRect`, `HeatmapCircle`, `Graph`, `LinePath`, `AreaClosed`, and `Bar` components in the hub previews.
  - Reason: functionally equivalent SVG/D3 surfaces were used for speed and React 19 compatibility. The user-facing visuals requested in the spec are implemented; only the internal primitive choice differs.
- [ ] Browser/in-app visual verification.
  - Reason: stopped per instruction. No further browser connection/testing was performed after the user asked to stop touching the in-app browser.
- [ ] API wiring.
  - Reason: not part of this request. Current changes are frontend route/hub/layout upgrades only.

### Validation Notes

- [x] `npm exec -- eslint src/app/labs/volatility-v2/page.js src/app/labs/volatility-v2/layout.js src/components/VolCommandPalette.jsx` passes after the final upgrade pass.
- [x] `curl -I http://127.0.0.1:3000/labs/volatility-v2` returns `HTTP/1.1 200 OK` after the final upgrade pass.
- [!] `npm install` reported existing audit vulnerabilities in the frontend dependency tree. I did not run `npm audit fix --force` because that can introduce breaking dependency changes unrelated to this UI upgrade.
- [!] `@visx/*` packages required `--legacy-peer-deps` because their published peer range stops at React 18 while this app is on React 19. They installed successfully.
- [!] Per user instruction, no in-app browser connection or visual browser verification was attempted in the final pass.

---

Let me look at what's actually being built in elite financial/quant UI right now.I have everything. Here is the full, complete, no-limits treatment. Every upgrade is specific to your actual 9 modules with exact npm installs, exact chart types, exact code.

---

## The Full God-Tier Upgrade Manifest

### The Stack to Install

```bash
npm install framer-motion @visx/heatmap @visx/network @visx/scale @visx/group @visx/shape @visx/axis @visx/gradient @visx/responsive react-plotly.js plotly.js-dist-min
```

---

## Part 1: Replace Recharts with the right tool per module

Your current code uses Recharts for everything. That is wrong. Here is what each of your 9 modules should render:

| Module | What to show | Package |
|--------|-------------|---------|
| V01 Estimators | Violin plot of estimator distributions + signature plot (variance vs lag) | `@visx/shape` + `@visx/scale` |
| V02 GARCH | 3D volatility term structure surface | `react-plotly.js` type `surface` |
| V03 HAR | Multi-horizon fan chart with bootstrap CI bands | Recharts `Area` stacked (fine to keep) |
| V04 Regimes | Regime probability heatmap over time (calendar-style) | `@visx/heatmap` `HeatmapRect` |
| V05 VRP | VRP scatter with regression line + confidence band | `@visx/shape` `LinePath` + `AreaClosed` |
| V06 Spillover | Force-directed spillover network graph | `@visx/network` |
| V07 DCC | 5x5 animated correlation matrix with hover slices | `@visx/heatmap` `HeatmapCircle` |
| V08 Stress | Waterfall chart (sequential bars) | `@visx/shape` `Bar` with D3 positioning |
| V09 Budget | Bullet chart (budget vs actual per asset) | `@visx/shape` custom |

---

## Part 2: The V02 GARCH 3D Volatility Surface (the signature piece)

This is the one that makes people stop scrolling. A proper 3D surface, draggable, dark-themed, amber colorscale. Zero Recharts.

```jsx
// Install: npm install react-plotly.js plotly.js-dist-min
// Use dynamic import in Next.js to avoid SSR issues:
// const Plot = dynamic(() => import('react-plotly.js'), { ssr: false })

import dynamic from 'next/dynamic';
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

function GarchVisual() {
  const horizons = [1, 5, 10, 21, 42, 63, 126, 252];
  const models  = ['GARCH', 'EGARCH', 'GJR', 'APARCH', 'FIGARCH'];

  // z[model_index][horizon_index]
  const z = models.map((_, mi) =>
    horizons.map((h, hi) =>
      0.14 + mi * 0.006 + Math.sin(hi / 2 + mi) * 0.018 + (hi > 5 ? 0.012 : 0)
    )
  );

  return (
    <Plot
      data={[{
        type: 'surface',
        x: horizons,
        y: models,
        z,
        colorscale: [
          [0,   '#0D0F0A'],
          [0.3, '#2A1F00'],
          [0.6, '#8B5C00'],
          [0.8, '#C88000'],
          [1.0, '#F5A400'],
        ],
        contours: {
          z: { show: true, usecolormap: true, highlightcolor: '#FFD166', project: { z: true } }
        },
        lighting: { ambient: 0.7, diffuse: 0.6, roughness: 0.5, fresnel: 0.2 },
        lightposition: { x: 100, y: 200, z: 0 },
        showscale: false,
      }]}
      layout={{
        paper_bgcolor: 'transparent',
        plot_bgcolor:  'transparent',
        margin: { l: 0, r: 0, t: 0, b: 0 },
        scene: {
          bgcolor: 'transparent',
          xaxis: { title: 'Horizon (d)', color: '#5A5448', gridcolor: '#1F1C15', showbackground: false },
          yaxis: { title: '',           color: '#5A5448', gridcolor: '#1F1C15', showbackground: false },
          zaxis: { title: 'σ forecast', color: '#5A5448', gridcolor: '#1F1C15', showbackground: false, tickformat: '.0%' },
          camera: { eye: { x: 1.6, y: -1.4, z: 0.9 } },
        },
        font: { family: 'JetBrains Mono, IBM Plex Mono, monospace', color: '#9E9688', size: 10 },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: '340px' }}
    />
  );
}
```

---

## Part 3: V04 Regime Calendar Heatmap with `@visx/heatmap`

Instead of a stacked area chart for regimes (which everyone does), render a calendar-style heatmap where each cell is a week and color = dominant regime. This is what quant risk desks actually use.

```jsx
import { HeatmapRect } from '@visx/heatmap';
import { scaleLinear, scaleBand } from '@visx/scale';
import { Group } from '@visx/group';

const REGIME_COLOR = {
  low:        '#22C55E',
  transition: '#60A5FA',
  high:       '#F5A400',
  crisis:     '#EF4444',
};

function RegimeVisual() {
  const weeks   = 52;
  const cols    = 13; // quarters across
  const rows    = 4;  // weeks per col block

  const data = Array.from({ length: cols }, (_, ci) =>
    Array.from({ length: rows }, (_, ri) => {
      const t = ci / cols;
      if (t > 0.82) return { regime: 'crisis',     v: 0.9 };
      if (t > 0.65) return { regime: 'high',       v: 0.7 };
      if (t > 0.35) return { regime: 'transition', v: 0.5 };
      return               { regime: 'low',        v: 0.2 };
    })
  );

  const cellW = 24;
  const cellH = 24;
  const gap   = 4;
  const width  = cols * (cellW + gap);
  const height = rows * (cellH + gap);

  return (
    <div className="vol-chart-shell">
      <header>
        <span>Regime calendar heatmap</span>
        <b aria-hidden="true" />
      </header>
      <div style={{ padding: '16px 12px', overflowX: 'auto' }}>
        <svg width={width} height={height + 32}>
          <Group>
            {data.map((col, ci) =>
              col.map((cell, ri) => (
                <rect
                  key={`${ci}-${ri}`}
                  x={ci * (cellW + gap)}
                  y={ri * (cellH + gap)}
                  width={cellW}
                  height={cellH}
                  rx={4}
                  fill={REGIME_COLOR[cell.regime]}
                  opacity={0.25 + cell.v * 0.65}
                >
                  <title>{`Q${Math.floor(ci/4)+1}W${ri+1}: ${cell.regime}`}</title>
                </rect>
              ))
            )}
          </Group>
          {/* regime legend */}
          {Object.entries(REGIME_COLOR).map(([label, color], i) => (
            <g key={label} transform={`translate(${i * 82}, ${height + 10})`}>
              <rect width={10} height={10} rx={2} fill={color} opacity={0.8} />
              <text x={14} y={9} fill="#5A5448"
                fontSize={9} fontFamily="JetBrains Mono, monospace"
                textTransform="uppercase" letterSpacing="0.08em">
                {label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
```

---

## Part 4: V06 Spillover — Force-Directed Network with `@visx/network`

Replace the static SVG lines you currently have with a proper force-positioned network. This is the visual that defines V06.

```bash
npm install @visx/network d3-force
```

```jsx
import { Graph } from '@visx/network';
import { useEffect, useRef, useState } from 'react';
import * as d3Force from 'd3-force';

const ASSETS = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM'];

// Spillover strengths (pairwise FEVD %)
const LINKS_RAW = [
  { source: 0, target: 1, value: 0.72 },
  { source: 1, target: 2, value: 0.41 },
  { source: 0, target: 3, value: 0.38 },
  { source: 2, target: 4, value: 0.55 },
  { source: 3, target: 4, value: 0.29 },
  { source: 0, target: 2, value: 0.62 },
  { source: 1, target: 4, value: 0.33 },
];

function ConnectednessVisual() {
  const W = 380, H = 300;
  const [nodes, setNodes] = useState(
    ASSETS.map((id, i) => ({
      id, i,
      x: W / 2 + Math.cos((i / ASSETS.length) * 2 * Math.PI) * 100,
      y: H / 2 + Math.sin((i / ASSETS.length) * 2 * Math.PI) * 90,
      // net transmitter score
      score: [0.72 + 0.62, 0.72 + 0.41 + 0.33, 0.41 + 0.55 + 0.62, 0.38 + 0.29, 0.55 + 0.29 + 0.33][i],
    }))
  );

  useEffect(() => {
    const sim = d3Force.forceSimulation(nodes)
      .force('link', d3Force.forceLink(
        LINKS_RAW.map(l => ({ ...l, source: nodes[l.source], target: nodes[l.target] }))
      ).distance(110).strength(0.4))
      .force('charge', d3Force.forceManyBody().strength(-180))
      .force('center', d3Force.forceCenter(W / 2, H / 2))
      .force('collision', d3Force.forceCollide(32));

    sim.on('tick', () => setNodes([...sim.nodes()]));
    sim.on('end', () => sim.stop());
    return () => sim.stop();
  }, []); // eslint-disable-line

  const links = LINKS_RAW.map(l => ({
    source: nodes[l.source],
    target: nodes[l.target],
    value:  l.value,
  }));

  return (
    <div className="vol-chart-shell">
      <header>
        <span>Spillover network · DY-GFEVD</span>
        <b aria-hidden="true" />
      </header>
      <div style={{ padding: '8px' }}>
        <svg width={W} height={H} style={{ overflow: 'visible' }}>
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="6"
              refX="16" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z"
                fill="rgba(245,164,0,0.5)" />
            </marker>
          </defs>
          {links.map((link, i) => (
            <line key={i}
              x1={link.source.x} y1={link.source.y}
              x2={link.target.x} y2={link.target.y}
              stroke="rgba(245,164,0,0.22)"
              strokeWidth={link.value * 4}
              markerEnd="url(#arrow)"
            />
          ))}
          {nodes.map((node) => {
            const r = 14 + node.score * 8;
            const isTransmitter = node.score > 1;
            return (
              <g key={node.id} transform={`translate(${node.x},${node.y})`}>
                <circle r={r + 8} fill={isTransmitter
                  ? 'rgba(239,68,68,0.08)' : 'rgba(245,164,0,0.06)'} />
                <circle r={r}
                  fill="#0D0F0A"
                  stroke={isTransmitter ? '#EF4444' : '#F5A400'}
                  strokeWidth={isTransmitter ? 2 : 1.5} />
                <text textAnchor="middle" dominantBaseline="middle"
                  fill={isTransmitter ? '#EF4444' : '#F0EDE4'}
                  fontSize={10} fontFamily="JetBrains Mono, monospace"
                  fontWeight={900}>
                  {node.id}
                </text>
                <text textAnchor="middle" y={r + 14}
                  fill="#5A5448" fontSize={8}
                  fontFamily="JetBrains Mono, monospace">
                  {(node.score * 100).toFixed(0)}%
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
```

---

## Part 5: V07 DCC — `@visx/heatmap` circle matrix with hover cross-section

Replace your current flat span grid with an actual interactive heatmap. Hovering a cell shows the full row + column slice (the Bloomberg DCC interaction).

```jsx
import { HeatmapCircle } from '@visx/heatmap';
import { scaleLinear } from '@visx/scale';
import { Group } from '@visx/group';
import { useState } from 'react';

const TICKERS = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM'];

const corrMatrix = TICKERS.flatMap((r, i) =>
  TICKERS.map((c, j) => ({
    row: i, col: j,
    v: i === j ? 1 : Math.max(-0.15,
      Math.min(0.96, 0.78 - Math.abs(i - j) * 0.13 + Math.sin((i + j) * 1.7) * 0.08))
  }))
);

function DccVisual() {
  const [hover, setHover] = useState(null); // { row, col }
  const N   = TICKERS.length;
  const SZ  = 52; // cell size
  const PAD = 36;
  const W   = N * SZ + PAD;
  const H   = N * SZ + PAD;

  const colorScale = scaleLinear({
    domain: [-0.2, 0, 1],
    range:  ['#60A5FA', '#0D0F0A', '#F5A400'],
  });

  return (
    <div className="vol-chart-shell">
      <header>
        <span>DCC correlation matrix</span>
        <b aria-hidden="true" />
      </header>
      <div style={{ padding: '12px 8px', display: 'flex', justifyContent: 'center' }}>
        <svg width={W} height={H}>
          {/* axis labels */}
          {TICKERS.map((t, i) => (
            <g key={t}>
              <text x={PAD + i * SZ + SZ / 2} y={14}
                textAnchor="middle" fill="#5A5448"
                fontSize={9} fontFamily="JetBrains Mono, monospace" fontWeight={900}>
                {t}
              </text>
              <text x={PAD - 6} y={PAD + i * SZ + SZ / 2 + 4}
                textAnchor="end" fill="#5A5448"
                fontSize={9} fontFamily="JetBrains Mono, monospace" fontWeight={900}>
                {t}
              </text>
            </g>
          ))}
          {corrMatrix.map(({ row, col, v }) => {
            const isHovered = hover && (hover.row === row || hover.col === col);
            const isSelf    = row === col;
            const cx = PAD + col * SZ + SZ / 2;
            const cy = PAD + row * SZ + SZ / 2;
            const r  = (SZ / 2 - 4) * (isSelf ? 1 : 0.4 + Math.abs(v) * 0.56);
            return (
              <circle key={`${row}-${col}`}
                cx={cx} cy={cy} r={r}
                fill={colorScale(v)}
                opacity={isHovered ? 1 : isSelf ? 0.9 : 0.72}
                stroke={isHovered ? 'rgba(245,164,0,0.6)' : 'none'}
                strokeWidth={1.5}
                style={{ cursor: 'crosshair', transition: 'opacity 120ms, r 120ms' }}
                onMouseEnter={() => setHover({ row, col })}
                onMouseLeave={() => setHover(null)}
              >
                <title>{`${TICKERS[row]} / ${TICKERS[col]}: ${v.toFixed(3)}`}</title>
              </circle>
            );
          })}
          {/* value label on hover */}
          {hover && (() => {
            const cell = corrMatrix.find(c => c.row === hover.row && c.col === hover.col);
            return (
              <text
                x={PAD + hover.col * SZ + SZ / 2}
                y={PAD + hover.row * SZ + SZ / 2 + 4}
                textAnchor="middle"
                fill="#F5F2EA"
                fontSize={9}
                fontFamily="JetBrains Mono, monospace"
                fontWeight={900}
                pointerEvents="none">
                {cell.v.toFixed(2)}
              </text>
            );
          })()}
        </svg>
      </div>
    </div>
  );
}
```

---

## Part 6: Framer Motion — replace the IntersectionObserver card reveal

Your current scroll reveal is a manual `in-view` CSS class toggle. Replace with Framer Motion for proper staggered orchestration with spring physics.

```bash
npm install framer-motion
```

```jsx
import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

// REPLACE the FeatureCard component entirely
function FeatureCard({ feature, flip, onPreview }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-15% 0px -15% 0px' });

  return (
    <motion.section
      ref={ref}
      className={`vol-feature-card ${flip ? 'flip' : ''}`}
      initial={{ opacity: 0, y: 32 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="vol-feature-copy">
        <p>V{feature.id} · {feature.tag}</p>
        <h2>{feature.title}</h2>
        <span>{feature.description}</span>
        <ul>
          {feature.bullets.map((b, i) => (
            <motion.li key={b}
              initial={{ opacity: 0, x: -12 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ delay: 0.18 + i * 0.07, duration: 0.38, ease: [0.16, 1, 0.3, 1] }}>
              {b}
            </motion.li>
          ))}
        </ul>
        <div className="vol-feature-actions">
          <Link href={`/labs/volatility-v2/feature-${feature.id}`}>
            Open Module <ExternalLink size={14} />
          </Link>
          <button onClick={() => onPreview(feature.id)} type="button">
            <Eye size={14} /> Preview
          </button>
        </div>
      </div>
      <motion.div
        className="vol-feature-visual"
        initial={{ opacity: 0, scale: 0.97 }}
        animate={inView ? { opacity: 1, scale: 1 } : {}}
        transition={{ delay: 0.12, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}>
        {feature.visual}
        <div className="vol-watermark">V{feature.id}</div>
      </motion.div>
    </motion.section>
  );
}
```

Also remove the `useEffect` that used `querySelectorAll(".vol-feature-card")` and the IntersectionObserver — Framer handles it.

Remove `.vol-feature-card { opacity: 0; transform: translateY(24px); }` and `.vol-feature-card.in-view` from the CSS — Framer owns that now.

---

## Part 7: Shadcn "sliding number" style digit roller for the stats bar

Replace your `CountUp` with a digit-by-digit mechanical odometer. From the shadcn registry.

```bash
npm install motion
```

```jsx
// REPLACE the CountUp component
import { useSpring, animated } from '@react-spring/web';
import { useInView } from 'framer-motion';
import { useRef, useEffect, useState } from 'react';

function SlottedNumber({ value, suffix = '' }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [started, setStarted] = useState(false);

  useEffect(() => { if (inView) setStarted(true); }, [inView]);

  const { v } = useSpring({
    from: { v: 0 },
    to:   { v: started ? value : 0 },
    config: { tension: 60, friction: 22 },
  });

  return (
    <animated.span ref={ref}
      style={{
        fontVariantNumeric: 'tabular-nums slashed-zero',
        fontFeatureSettings: '"tnum" 1, "zero" 1',
      }}>
      {v.to(n => `${Math.round(n).toLocaleString()}${suffix}`)}
    </animated.span>
  );
}
```

Install `@react-spring/web`:
```bash
npm install @react-spring/web
```

---

## Part 8: The hero — replace the static SVG network with a canvas particle field

Your `HeroNetwork` is a static SVG. Replace with a `<canvas>` particle system where nodes drift and connections form/break based on distance. 60fps, `requestAnimationFrame`, ~40 lines.

```jsx
import { useEffect, useRef } from 'react';

function HeroCanvas() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width  = W;
    canvas.height = H;

    const AMBER = 'rgba(245,164,0,';
    const RED   = 'rgba(239,68,68,';
    const N = 28;

    const nodes = Array.from({ length: N }, (_, i) => ({
      x:  Math.random() * W,
      y:  Math.random() * H,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      r:  2.5 + Math.random() * 3,
      hot: i < 4, // first 4 are "transmitters" in red
    }));

    let raf;
    function draw() {
      ctx.clearRect(0, 0, W, H);

      // edges
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          const dx   = nodes[i].x - nodes[j].x;
          const dy   = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 130) {
            const alpha = (1 - dist / 130) * 0.18;
            const color = (nodes[i].hot || nodes[j].hot) ? RED : AMBER;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `${color}${alpha})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      // nodes
      nodes.forEach(node => {
        const color = node.hot ? RED : AMBER;
        // glow
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r + 6, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0.06)`;
        ctx.fill();
        // core
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0.85)`;
        ctx.fill();

        node.x += node.vx;
        node.y += node.vy;
        if (node.x < 0 || node.x > W) node.vx *= -1;
        if (node.y < 0 || node.y > H) node.vy *= -1;
      });

      raf = requestAnimationFrame(draw);
    }

    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="hero-vol-canvas"
      aria-hidden="true"
    />
  );
}
```

CSS to add:

```css
/* REPLACE .hero-vol-network with this */
.hero-vol-canvas {
  position: absolute;
  right: 0;
  top: 0;
  width: min(520px, 40vw);
  height: 100%;
  opacity: 0.55;
  pointer-events: none;
  z-index: 0;
}
```

---

## Part 9: The V01 Estimator — replace with a proper signature plot

A signature plot is THE standard for demonstrating estimator noise. It plots realized variance vs sampling frequency on a log-log axis. Replace the current area chart in `EstimatorVisual`.

```jsx
// Pure SVG, no library needed, data is synthetic
function EstimatorVisual() {
  const W = 400, H = 280;
  const freqs = [1, 2, 5, 10, 15, 30, 60, 120, 390]; // sampling freq in mins
  
  // Yang-Zhang, Parkinson, Close-to-Close at each frequency
  const yz  = freqs.map((f, i) => 0.155 + (i < 3 ? 0.04 / f : 0.001 * i));
  const pk  = freqs.map((f, i) => 0.148 + (i < 4 ? 0.02 / f : 0.001 * i));
  const c2c = freqs.map((f, i) => 0.14  + (i < 5 ? 0.01 / f : 0.0015 * i));

  const xScale = (i) => 40 + (i / (freqs.length - 1)) * (W - 60);
  const yScale = (v) => H - 30 - ((v - 0.13) / 0.08) * (H - 60);

  const path = (vals) =>
    vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ');

  return (
    <div className="vol-chart-shell">
      <header>
        <span>Signature plot · RV vs sampling freq</span>
        <b aria-hidden="true" />
      </header>
      <div style={{ padding: '12px 8px' }}>
        <svg width={W} height={H} style={{ overflow: 'visible' }}>
          {/* grid */}
          {[0.14, 0.16, 0.18, 0.20].map(v => (
            <g key={v}>
              <line x1={40} x2={W - 20} y1={yScale(v)} y2={yScale(v)}
                stroke="#1F1C15" strokeWidth={1} />
              <text x={34} y={yScale(v) + 4} textAnchor="end"
                fill="#5A5448" fontSize={9} fontFamily="JetBrains Mono, monospace">
                {(v * 100).toFixed(0)}%
              </text>
            </g>
          ))}

          {/* x labels */}
          {freqs.map((f, i) => (
            <text key={f} x={xScale(i)} y={H - 8} textAnchor="middle"
              fill="#5A5448" fontSize={8} fontFamily="JetBrains Mono, monospace">
              {f}m
            </text>
          ))}

          {/* Microstructure noise band */}
          <path d={`${path(yz.map(v => v + 0.008))} L${xScale(freqs.length-1)},${yScale(yz[freqs.length-1] - 0.008)} ${path(yz.map((v,i) => v - 0.008)).split('M').join('L')} Z`}
            fill="rgba(245,164,0,0.06)" />

          {/* Lines */}
          <path d={path(yz)}  stroke="#F5A400" strokeWidth={2} fill="none" strokeLinejoin="round" />
          <path d={path(pk)}  stroke="#22C55E" strokeWidth={1.5} fill="none" strokeLinejoin="round" strokeDasharray="5 3" />
          <path d={path(c2c)} stroke="#60A5FA" strokeWidth={1.5} fill="none" strokeLinejoin="round" strokeDasharray="2 4" />

          {/* Efficient price level annotation */}
          <line x1={xScale(5)} x2={xScale(5)} y1={30} y2={H - 30}
            stroke="rgba(245,164,0,0.2)" strokeWidth={1} strokeDasharray="3 3" />
          <text x={xScale(5) + 6} y={48}
            fill="rgba(245,164,0,0.5)" fontSize={8}
            fontFamily="JetBrains Mono, monospace">
            Efficient
          </text>

          {/* Legend */}
          {[['YZ', '#F5A400'], ['PK', '#22C55E'], ['C2C', '#60A5FA']].map(([label, color], i) => (
            <g key={label} transform={`translate(${50 + i * 60}, 22)`}>
              <line x1={0} x2={16} y1={0} y2={0} stroke={color} strokeWidth={1.5} />
              <text x={20} y={4} fill="#9E9688" fontSize={9}
                fontFamily="JetBrains Mono, monospace">{label}</text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
```

---

## Part 10: The cluster intro — scroll-linked parallax section number

The `0N` ghost number behind each cluster should parallax at 0.4x scroll speed using Framer `useScroll` + `useTransform`.

```jsx
import { motion, useScroll, useTransform } from 'framer-motion';
import { useRef } from 'react';

// REPLACE ClusterIntro
function ClusterIntro({ cluster, index }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });
  const y = useTransform(scrollYProgress, [0, 1], ['10%', '-10%']);

  return (
    <section className="vol-cluster" ref={ref} id={cluster.id}>
      <div style={{ position: 'relative', overflow: 'hidden' }}>
        <motion.span
          className="vol-cluster-ghost"
          style={{ y }}
          aria-hidden="true">
          0{index + 1}
        </motion.span>
        <p>{cluster.label}</p>
        <h2>{cluster.title}</h2>
        <span>{cluster.description}</span>
      </div>
      <div className="vol-cluster-pills">
        {cluster.ids.map((id) => {
          const feature = features.find(f => f.id === id);
          return (
            <Link href={`/labs/volatility-v2/feature-${id}`} key={id}>
              <i />V{id} {feature?.tag}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
```

Update the render call to pass `index`:
```jsx
// In the blocks.map, change the cluster render to:
<ClusterIntro cluster={block.cluster} index={clusterIndex++} key={block.cluster.id} />
// and declare let clusterIndex = 0; before the map
```

CSS:
```css
/* ADD */
.vol-cluster-ghost {
  position: absolute;
  top: -0.15em;
  left: -0.08em;
  font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
  font-size: clamp(110px, 16vw, 210px);
  font-weight: 950;
  line-height: 1;
  color: transparent;
  -webkit-text-stroke: 1px rgba(245, 164, 0, 0.07);
  pointer-events: none;
  user-select: none;
  will-change: transform;
  z-index: 0;
}

.vol-cluster > div:first-child > *:not(.vol-cluster-ghost) {
  position: relative;
  z-index: 1;
}
```

---

That is the complete treatment. The packages in priority order:

1. `framer-motion` — do this first, it transforms every card
2. `react-plotly.js plotly.js-dist-min` — gets you the 3D GARCH surface
3. `@visx/heatmap @visx/network @visx/scale @visx/group @visx/shape` — gets you DCC circles + spillover network
4. `d3-force` — needed for the network simulation
5. `@react-spring/web` — odometer stat numbers


I have everything I need. Here is the complete, no-limits upgrade manifest. Everything is specific, specific to your 9 modules, specific packages, specific code.

---

## Install everything at once

```bash
npm install cmdk framer-motion @react-spring/web react-plotly.js plotly.js-dist-min @visx/heatmap @visx/network @visx/scale @visx/group @visx/shape @visx/axis @visx/gradient @visx/responsive d3-force react-grid-layout react-resizable
```

---

## Upgrade 1: The ⌘K Command Palette (the biggest single feature you can add)

Your strip already has `⌘K` badge sitting there doing nothing. Wire it up. This is what makes the whole thing feel like an actual terminal product. Use `cmdk` directly, styled from scratch, no Tailwind.

```bash
npm install cmdk
```

Create `components/VolCommandPalette.jsx`:

```jsx
"use client";

import { Command } from "cmdk";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink } from "lucide-react";

const COMMANDS = [
  // Navigation
  { group: "MODULES", id: "v01", label: "V01 · Estimators",     sub: "Yang-Zhang, Parkinson, GK, RS, C2C",  href: "/labs/volatility-v2/feature-01" },
  { group: "MODULES", id: "v02", label: "V02 · GARCH Suite",     sub: "GARCH / EGARCH / GJR / FIGARCH",      href: "/labs/volatility-v2/feature-02" },
  { group: "MODULES", id: "v03", label: "V03 · HAR Forecast",    sub: "Multi-horizon walk-forward",          href: "/labs/volatility-v2/feature-03" },
  { group: "MODULES", id: "v04", label: "V04 · Regime Detection",sub: "HMM / SJM probability stack",         href: "/labs/volatility-v2/feature-04" },
  { group: "MODULES", id: "v05", label: "V05 · VRP Monitor",     sub: "Implied vs physical premium",         href: "/labs/volatility-v2/feature-05" },
  { group: "MODULES", id: "v06", label: "V06 · Spillover",       sub: "Diebold-Yilmaz GFEVD network",       href: "/labs/volatility-v2/feature-06" },
  { group: "MODULES", id: "v07", label: "V07 · DCC Engine",      sub: "DCC-MLE / MIDAS correlation",         href: "/labs/volatility-v2/feature-07" },
  { group: "MODULES", id: "v08", label: "V08 · Stress Engine",   sub: "Scenario P&L, reverse stress",        href: "/labs/volatility-v2/feature-08" },
  { group: "MODULES", id: "v09", label: "V09 · Vol Budget",      sub: "Target-vol scaling, rebalance",       href: "/labs/volatility-v2/feature-09" },
  // Clusters
  { group: "CLUSTERS", id: "c1", label: "Estimation & Forecasting", sub: "V01 + V02 + V03", href: "#estimation-forecasting" },
  { group: "CLUSTERS", id: "c2", label: "Regimes & Risk Premium",   sub: "V04 + V05",       href: "#regime-premium"        },
  { group: "CLUSTERS", id: "c3", label: "Connectedness & Stress",   sub: "V06 + V07 + V08", href: "#systemic-covariance"   },
  { group: "CLUSTERS", id: "c4", label: "Portfolio Control",        sub: "V09",             href: "#portfolio-control"     },
  // Actions
  { group: "ACTIONS", id: "a1", label: "Open V01 live shell", sub: "Start with Yang-Zhang estimator", href: "/labs/volatility-v2/feature-01" },
  { group: "ACTIONS", id: "a2", label: "Jump to DCC Engine",  sub: "Multi-asset covariance",          href: "/labs/volatility-v2/feature-07" },
];

export function VolCommandPalette() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const router = useRouter();

  useEffect(() => {
    const down = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  // Also let the ⌘K badge click open it
  useEffect(() => {
    const badge = document.querySelector(".vol-cmd-badge");
    if (!badge) return;
    const click = () => setOpen(true);
    badge.addEventListener("click", click);
    badge.style.cursor = "pointer";
    return () => badge.removeEventListener("click", click);
  }, []);

  const groups = [...new Set(COMMANDS.map((c) => c.group))];
  const filtered = COMMANDS.filter(
    (c) =>
      !search ||
      c.label.toLowerCase().includes(search.toLowerCase()) ||
      c.sub.toLowerCase().includes(search.toLowerCase())
  );

  if (!open) return null;

  return (
    <>
      <div className="vol-cmdk-backdrop" onClick={() => setOpen(false)} />
      <div className="vol-cmdk-shell" role="dialog" aria-modal="true" aria-label="Command palette">
        <Command label="Volatility command palette" shouldFilter={false}>
          <div className="vol-cmdk-input-wrap">
            <span className="vol-cmdk-input-icon">
              {/* search slash */}
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </span>
            <Command.Input
              className="vol-cmdk-input"
              placeholder="Search modules, clusters, actions..."
              value={search}
              onValueChange={setSearch}
              autoFocus
            />
            <kbd className="vol-cmdk-esc">ESC</kbd>
          </div>

          <Command.List className="vol-cmdk-list">
            <Command.Empty className="vol-cmdk-empty">
              No results for &ldquo;{search}&rdquo;
            </Command.Empty>

            {groups.map((group) => {
              const items = filtered.filter((c) => c.group === group);
              if (!items.length) return null;
              return (
                <Command.Group key={group} heading={group} className="vol-cmdk-group">
                  {items.map((cmd) => (
                    <Command.Item
                      key={cmd.id}
                      className="vol-cmdk-item"
                      onSelect={() => {
                        setOpen(false);
                        if (cmd.href.startsWith("#")) {
                          document.getElementById(cmd.href.slice(1))?.scrollIntoView({ behavior: "smooth" });
                        } else {
                          router.push(cmd.href);
                        }
                      }}
                    >
                      <span className="vol-cmdk-item-label">{cmd.label}</span>
                      <span className="vol-cmdk-item-sub">{cmd.sub}</span>
                      <ExternalLink size={11} className="vol-cmdk-item-arrow" />
                    </Command.Item>
                  ))}
                </Command.Group>
              );
            })}
          </Command.List>

          <div className="vol-cmdk-footer">
            <span><kbd>↑↓</kbd> navigate</span>
            <span><kbd>↵</kbd> open</span>
            <span><kbd>ESC</kbd> close</span>
            <span style={{ marginLeft: "auto", color: "rgba(245,164,0,0.5)", fontWeight: 900 }}>
              ATLAS · VOL INTELLIGENCE
            </span>
          </div>
        </Command>
      </div>
    </>
  );
}
```

Add to `VolatilityV2Layout` right before the closing `</div>`:

```jsx
import { VolCommandPalette } from "@/components/VolCommandPalette";

// Inside VolatilityV2Layout return:
<div className="volatility-v2-shell">
  {children}
  <VolatilityStrip />
  <VolCommandPalette />   {/* ADD THIS */}
  <style ...>
```

CSS (add into the layout's global style block):

```css
/* ── Command Palette ──────────────────────────────────────────── */
.vol-cmdk-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(6px);
  animation: cmdkFadeIn 120ms ease;
}

@keyframes cmdkFadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.vol-cmdk-shell {
  position: fixed;
  top: 18vh;
  left: 50%;
  transform: translateX(-50%);
  z-index: 201;
  width: min(680px, calc(100vw - 32px));
  border: 1px solid rgba(245, 164, 0, 0.28);
  border-radius: 16px;
  background: rgba(8, 7, 5, 0.97);
  box-shadow:
    0 0 0 1px rgba(245, 164, 0, 0.06) inset,
    0 40px 120px rgba(0, 0, 0, 0.8),
    0 0 80px rgba(245, 164, 0, 0.04);
  overflow: hidden;
  animation: cmdkSlideIn 160ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cmdkSlideIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-12px) scale(0.98); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
}

.vol-cmdk-input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid #1A1710;
  height: 54px;
}

.vol-cmdk-input-icon {
  color: #5A5448;
  flex: 0 0 auto;
}

.vol-cmdk-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #F0EDE4;
  font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
  font-size: 14px;
  font-weight: 500;
  caret-color: #F5A400;
}

.vol-cmdk-input::placeholder {
  color: #3A3530;
}

.vol-cmdk-esc {
  padding: 3px 7px;
  border: 1px solid #2A2218;
  border-radius: 5px;
  background: #0D0B08;
  color: #5A5448;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 700;
}

.vol-cmdk-list {
  max-height: 400px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #2A2218 transparent;
  padding: 6px 0;
}

.vol-cmdk-group [cmdk-group-heading] {
  padding: 8px 16px 4px;
  color: #3A3530;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.vol-cmdk-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  border-radius: 0;
  transition: background 80ms ease;
}

.vol-cmdk-item[aria-selected="true"],
.vol-cmdk-item:hover {
  background: rgba(245, 164, 0, 0.07);
  outline: none;
}

.vol-cmdk-item[aria-selected="true"] .vol-cmdk-item-label {
  color: #F5A400;
}

.vol-cmdk-item-label {
  color: #F0EDE4;
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  flex: 0 0 auto;
}

.vol-cmdk-item-sub {
  color: #5A5448;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vol-cmdk-item-arrow {
  color: #3A3530;
  flex: 0 0 auto;
}

.vol-cmdk-item[aria-selected="true"] .vol-cmdk-item-arrow {
  color: #F5A400;
}

.vol-cmdk-empty {
  padding: 28px 16px;
  text-align: center;
  color: #3A3530;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}

.vol-cmdk-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  border-top: 1px solid #1A1710;
  background: #070604;
}

.vol-cmdk-footer span {
  color: #3A3530;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 5px;
}

.vol-cmdk-footer kbd {
  padding: 2px 5px;
  border: 1px solid #2A2218;
  border-radius: 4px;
  background: #0D0B08;
  color: #5A5448;
  font-family: "JetBrains Mono", monospace;
  font-size: 9px;
}
```

---

## Upgrade 2: `react-grid-layout` mode on the feature-page previews (Bloomberg multi-panel)

This is the one that crosses from "nice landing page" into "actual terminal". On the main hub page, add a `LAYOUT` toggle button at the top of `.vol-stack`. When active, all 9 module visual panels become a draggable, resizable bloomberg-style grid. When off, normal scroll layout.

```bash
npm install react-grid-layout react-resizable
```

Add to the page:

```jsx
// At the top of VolatilityV2HomePage, add state:
const [gridMode, setGridMode] = useState(false);

// In the return, right after <FeatureTabStrip />:
<div className="vol-layout-toggle-bar">
  <span className="vol-layout-toggle-label">VIEW</span>
  <button
    className={`vol-layout-btn ${!gridMode ? "active" : ""}`}
    onClick={() => setGridMode(false)}
    type="button"
  >
    STACK
  </button>
  <button
    className={`vol-layout-btn ${gridMode ? "active" : ""}`}
    onClick={() => setGridMode(true)}
    type="button"
  >
    GRID
  </button>
</div>
```

Then add the `GridDashboard` component that renders when `gridMode` is true:

```jsx
import GridLayout from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

function GridDashboard() {
  const cols = 12;
  const defaultLayout = [
    { i: "01", x: 0,  y: 0, w: 4, h: 8,  minW: 3, minH: 6 },
    { i: "02", x: 4,  y: 0, w: 4, h: 8,  minW: 3, minH: 6 },
    { i: "03", x: 8,  y: 0, w: 4, h: 8,  minW: 3, minH: 6 },
    { i: "04", x: 0,  y: 8, w: 6, h: 9,  minW: 3, minH: 6 },
    { i: "05", x: 6,  y: 8, w: 6, h: 9,  minW: 3, minH: 6 },
    { i: "06", x: 0, y: 17, w: 4, h: 9,  minW: 3, minH: 6 },
    { i: "07", x: 4, y: 17, w: 4, h: 9,  minW: 3, minH: 6 },
    { i: "08", x: 8, y: 17, w: 4, h: 9,  minW: 3, minH: 6 },
    { i: "09", x: 0, y: 26, w: 12, h: 8, minW: 4, minH: 6 },
  ];

  return (
    <div className="vol-grid-dashboard">
      <GridLayout
        className="vol-rgl"
        layout={defaultLayout}
        cols={cols}
        rowHeight={44}
        width={1400}
        margin={[8, 8]}
        containerPadding={[16, 16]}
        draggableHandle=".vol-grid-drag-handle"
      >
        {features.map((f) => (
          <div key={f.id} className="vol-grid-panel">
            <div className="vol-grid-drag-handle">
              <div className="vol-grid-dots">
                <span /><span /><span />
              </div>
              <span>V{f.id} · {f.tag}</span>
              <a href={`/labs/volatility-v2/feature-${f.id}`}
                className="vol-grid-open">
                ↗
              </a>
            </div>
            <div className="vol-grid-content">
              {f.visual}
            </div>
          </div>
        ))}
      </GridLayout>
    </div>
  );
}
```

In the main return, conditionally render:

```jsx
{gridMode ? (
  <GridDashboard />
) : (
  <div className="vol-stack">
    {blocks.map((block) => (
      block.type === "cluster"
        ? <ClusterIntro ... />
        : <FeatureCard ... />
    ))}
  </div>
)}
```

CSS for the grid mode:

```css
/* ── Layout Toggle Bar ────────────────────────────────────────── */
.vol-layout-toggle-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px clamp(18px, 4vw, 56px);
  border-bottom: 1px solid #181410;
  background: #080706;
}

.vol-layout-toggle-label {
  color: #3A3530;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.2em;
  margin-right: 4px;
}

.vol-layout-btn {
  height: 28px;
  padding: 0 12px;
  border: 1px solid #2A2218;
  border-radius: 6px;
  background: transparent;
  color: #5A5448;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.12em;
  cursor: pointer;
  transition: all 120ms ease;
}

.vol-layout-btn.active {
  border-color: rgba(245, 164, 0, 0.4);
  background: rgba(245, 164, 0, 0.08);
  color: #F5A400;
}

/* ── Grid Dashboard ───────────────────────────────────────────── */
.vol-grid-dashboard {
  overflow-x: auto;
  padding: 16px;
  min-height: 80vh;
}

.vol-rgl {
  /* override react-grid-layout defaults to match dark theme */
}

/* override RGL placeholder while dragging */
.react-grid-placeholder {
  background: rgba(245, 164, 0, 0.08) !important;
  border: 1px dashed rgba(245, 164, 0, 0.3) !important;
  border-radius: 10px !important;
  opacity: 1 !important;
}

.vol-grid-panel {
  display: grid;
  grid-template-rows: 38px 1fr;
  border: 1px solid #1F1C15;
  border-radius: 10px;
  background: #090908;
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
  transition: border-color 150ms ease;
}

.vol-grid-panel:hover {
  border-color: rgba(245, 164, 0, 0.22);
}

.vol-grid-drag-handle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border-bottom: 1px solid #1A1710;
  background: #0C0B08;
  cursor: grab;
  user-select: none;
}

.vol-grid-drag-handle:active { cursor: grabbing; }

.vol-grid-dots {
  display: flex;
  gap: 4px;
  flex: 0 0 auto;
}

.vol-grid-dots span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #2A2218;
}

.vol-grid-drag-handle span:not(.vol-grid-dots span) {
  flex: 1;
  color: #5A5448;
  font-family: "JetBrains Mono", monospace;
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vol-grid-open {
  color: #3A3530;
  font-size: 13px;
  text-decoration: none;
  flex: 0 0 auto;
  transition: color 120ms ease;
}

.vol-grid-open:hover { color: #F5A400; }

.vol-grid-content {
  overflow: hidden;
  padding: 4px;
  min-height: 0;
}

/* override resize handle dot */
.react-resizable-handle {
  width: 14px !important;
  height: 14px !important;
}

.react-resizable-handle::after {
  border-color: #3A3530 !important;
  width: 6px !important;
  height: 6px !important;
}
```

---

## Upgrade 3: The floating ambient glow that follows mouse on the entire page

Not on individual cards. On the whole page. One `mousemove` listener sets `--gx` and `--gy` on `body`, a pseudo-element follows. This is what makes Linear's background feel alive.

Add one `useEffect` to `VolatilityV2HomePage`:

```jsx
useEffect(() => {
  const onMove = (e) => {
    document.documentElement.style.setProperty("--gx", `${e.clientX}px`);
    document.documentElement.style.setProperty("--gy", `${e.clientY}px`);
  };
  window.addEventListener("mousemove", onMove, { passive: true });
  return () => window.removeEventListener("mousemove", onMove);
}, []);
```

Add to the global CSS:

```css
/* ── Page-level ambient cursor glow ──────────────────────────── */
:root {
  --gx: 50vw;
  --gy: 50vh;
}

.vol-home::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background: radial-gradient(
    600px circle at var(--gx) var(--gy),
    rgba(245, 164, 0, 0.035),
    transparent 70%
  );
  will-change: background;
}

/* make sure all .vol-home children sit above it */
.vol-home > * {
  position: relative;
  z-index: 1;
}
```

---

## Upgrade 4: A simulated "ATLAS terminal" drawer that slides up from the strip

When the user presses `/` (forward slash, the Bloomberg convention for function entry), a terminal-style input drawer slides up from the bottom strip. It takes "commands" like `VRP CHART`, `GARCH 02`, `REGIME NOW` and routes to the relevant feature page. It's not real execution, but it looks and feels like Bloomberg's function line.

```jsx
// Add to VolatilityV2Layout (not the page):

function TerminalDrawer() {
  const [open, setOpen] = useState(false);
  const [val, setVal]   = useState("");
  const [history, setHistory] = useState([
    { type: "sys", text: "ATLAS VOL v2.0 · 9 modules loaded · type a command or press ESC" },
  ]);
  const inputRef = useRef(null);
  const router = typeof window !== "undefined" && require("next/navigation").useRouter
    ? require("next/navigation").useRouter()
    : null;

  useEffect(() => {
    const down = (e) => {
      if (e.key === "/" && !e.metaKey && !e.ctrlKey &&
          document.activeElement?.tagName !== "INPUT" &&
          document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape") { setOpen(false); setVal(""); }
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 60);
  }, [open]);

  const ROUTES = {
    "01": "/labs/volatility-v2/feature-01",
    "02": "/labs/volatility-v2/feature-02",
    "03": "/labs/volatility-v2/feature-03",
    "04": "/labs/volatility-v2/feature-04",
    "05": "/labs/volatility-v2/feature-05",
    "06": "/labs/volatility-v2/feature-06",
    "07": "/labs/volatility-v2/feature-07",
    "08": "/labs/volatility-v2/feature-08",
    "09": "/labs/volatility-v2/feature-09",
    "ESTIMATORS": "/labs/volatility-v2/feature-01",
    "GARCH":      "/labs/volatility-v2/feature-02",
    "HAR":        "/labs/volatility-v2/feature-03",
    "REGIME":     "/labs/volatility-v2/feature-04",
    "REGIMES":    "/labs/volatility-v2/feature-04",
    "VRP":        "/labs/volatility-v2/feature-05",
    "SPILLOVER":  "/labs/volatility-v2/feature-06",
    "DCC":        "/labs/volatility-v2/feature-07",
    "STRESS":     "/labs/volatility-v2/feature-08",
    "BUDGET":     "/labs/volatility-v2/feature-09",
    "HOME":       "/labs/volatility-v2",
  };

  const run = () => {
    const raw   = val.trim().toUpperCase();
    const token = raw.split(/\s+/)[0];
    const route = ROUTES[token] || ROUTES[raw];

    if (route) {
      setHistory((h) => [
        ...h,
        { type: "cmd", text: `> ${val}` },
        { type: "ok",  text: `→ Navigating to ${token}...` },
      ]);
      setVal("");
      setTimeout(() => {
        if (router) router.push(route);
        setOpen(false);
      }, 380);
    } else if (raw === "HELP") {
      setHistory((h) => [
        ...h,
        { type: "cmd", text: `> ${val}` },
        { type: "sys", text: "Commands: 01-09, ESTIMATORS, GARCH, HAR, REGIME, VRP, SPILLOVER, DCC, STRESS, BUDGET, HOME, CLEAR" },
      ]);
      setVal("");
    } else if (raw === "CLEAR") {
      setHistory([{ type: "sys", text: "ATLAS VOL v2.0 · cleared" }]);
      setVal("");
    } else if (raw) {
      setHistory((h) => [
        ...h,
        { type: "cmd", text: `> ${val}` },
        { type: "err", text: `Unknown function: ${raw} · type HELP for commands` },
      ]);
      setVal("");
    }
  };

  if (!open) return null;

  return (
    <div className="vol-terminal-drawer">
      <div className="vol-terminal-header">
        <span>ATLAS FUNCTION LINE</span>
        <span style={{ color: "#3A3530" }}>/ to open · ESC to close</span>
      </div>
      <div className="vol-terminal-history">
        {history.slice(-6).map((line, i) => (
          <div key={i} className={`vol-terminal-line vol-terminal-${line.type}`}>
            {line.text}
          </div>
        ))}
      </div>
      <div className="vol-terminal-input-row">
        <span className="vol-terminal-prompt">VOL&gt;</span>
        <input
          ref={inputRef}
          className="vol-terminal-input"
          value={val}
          onChange={(e) => setVal(e.target.value.toUpperCase())}
          onKeyDown={(e) => { if (e.key === "Enter") run(); }}
          placeholder="GARCH · DCC · 07 · HELP"
          spellCheck={false}
          autoComplete="off"
        />
        <button className="vol-terminal-run" onClick={run} type="button">
          EXEC ↵
        </button>
      </div>
    </div>
  );
}
```

Add `<TerminalDrawer />` alongside `<VolCommandPalette />` in the layout return.

CSS for the drawer:

```css
/* ── Terminal Drawer ─────────────────────────────────────────── */
.vol-terminal-drawer {
  position: fixed;
  left: 50%;
  bottom: 90px;
  transform: translateX(-50%);
  z-index: 85;
  width: min(780px, calc(100vw - 32px));
  border: 1px solid rgba(245, 164, 0, 0.32);
  border-radius: 14px;
  background: rgba(6, 5, 3, 0.97);
  box-shadow:
    0 0 0 1px rgba(245, 164, 0, 0.06) inset,
    0 -20px 60px rgba(0, 0, 0, 0.6);
  overflow: hidden;
  backdrop-filter: blur(20px);
  animation: termSlideUp 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes termSlideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}

.vol-terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #1A1710;
  background: #0A0907;
}

.vol-terminal-header span:first-child {
  color: #F5A400;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.2em;
}

.vol-terminal-header span:last-child {
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
}

.vol-terminal-history {
  padding: 10px 16px 6px;
  min-height: 72px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.vol-terminal-line {
  font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.vol-terminal-sys { color: #5A5448; }
.vol-terminal-cmd { color: #9E9688; }
.vol-terminal-ok  { color: #22C55E; }
.vol-terminal-err { color: #EF4444; }

.vol-terminal-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-top: 1px solid #1A1710;
  background: #080706;
}

.vol-terminal-prompt {
  color: #F5A400;
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
  font-weight: 900;
  flex: 0 0 auto;
}

.vol-terminal-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #F0EDE4;
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
  font-weight: 700;
  caret-color: #F5A400;
  letter-spacing: 0.06em;
  font-variant-numeric: tabular-nums;
}

.vol-terminal-input::placeholder {
  color: #2A2218;
  font-weight: 500;
}

.vol-terminal-run {
  padding: 5px 12px;
  border: 1px solid rgba(245, 164, 0, 0.3);
  border-radius: 6px;
  background: rgba(245, 164, 0, 0.08);
  color: #F5A400;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: background 120ms ease;
}

.vol-terminal-run:hover {
  background: rgba(245, 164, 0, 0.16);
}
```

---

## Priority order and what each gives you

| # | What | Package | Impact |
|---|------|---------|--------|
| 1 | ⌘K Command Palette | `cmdk` | Makes the whole thing product-grade overnight |
| 2 | `/` Terminal Function Line | none (built-in) | The one thing Bloomberg has that nothing else does |
| 3 | GRID mode with drag/resize | `react-grid-layout` | Turns hub into an actual terminal workspace |
| 4 | Page ambient cursor glow | none (CSS only) | Costs 8 lines, feels like Linear |

The terminal function line (upgrade 3) is the signature piece. No other financial web product has it. It costs zero dependencies and is the most "ATLAS" thing on this page.
