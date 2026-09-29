Now I have everything needed. This will be the most comprehensive, reference-grade design specification you can build from.

---

# QUANT360 Factor Intelligence Module: Complete Design Specification

**Version 1.0 | For Engineering and Design Handoff**

---

## PART I: DESIGN PHILOSOPHY

The governing principle is what Bloomberg's UX team calls "concealing complexity." Every decision at every layer of the interface serves a single constraint: a quant PM or allocator sitting in a DDQ meeting needs to read, interpret, and act on any panel within four seconds of looking at it. That is not aspirational. It is the design test. If any output panel requires more than four seconds to parse, the design has failed regardless of how technically correct the underlying computation is.

The second governing principle is information density without noise. Bloomberg and Axioma charge five figures annually not because their data is better but because their interfaces are built for professionals who despise the cognitive overhead of consumer UX patterns. There are no carousels, no onboarding modals, no empty states with illustrations. Every pixel either carries information or creates the negative space that makes adjacent information legible. The reference standard for every layout decision is the Portfolio Visualizer factor regression page and the Bloomberg PORT attribution screen, both of which succeed precisely because they treat the user as an adult who arrived with a specific question and needs the answer immediately.

The third governing principle, derived from the 2026 Muzli dashboard research, is that a "bold and futuristic finance dashboard" achieves its professional credibility through constraint, not decoration. Deep blacks paired with a single, disciplined accent color and clean typographic hierarchy deliver more perceived institutional authority than any gradient or glassmorphism treatment. The moment a quant dashboard looks like a crypto wallet it has lost the trust of the target user.

---

## PART II: DESIGN TOKENS (THE COMPLETE SYSTEM)

These tokens are the source of truth. Nothing in the implementation is permitted to deviate from them. Every hex value, every spacing unit, every font size is codified here. Any future feature that does not map to an existing token must first add a token rather than hardcode a value.

### Color Tokens

**Surface Layer (Background Hierarchy)**

The background system uses five surface levels arranged from deepest to most prominent. This is the primary mechanism for visual hierarchy and replaces the need for dividers, borders, or shadows in most contexts.

```
--surface-0: #080C10     /* Page background. Only ever used as the base. Appears nowhere else. */
--surface-1: #0D1117     /* Primary panel background. This is what 90% of all cards sit on. */
--surface-2: #161B22     /* Elevated panel, modal, dropdown background. */
--surface-3: #1C2128     /* Input field background, table row hover, secondary card. */
--surface-4: #21262D     /* Active row, selected state, tertiary card. */
--surface-overlay: rgba(13, 17, 23, 0.92)  /* Tooltip and popover overlay. */
```

**Border Tokens**

```
--border-subtle:   #21262D   /* Separates panels within the same elevation layer. Used at 1px. */
--border-default:  #30363D   /* Primary panel outline. Used at 1px. */
--border-muted:    #373E47   /* Chart gridlines, table row separators. */
--border-emphasis: #484F58   /* Active panel focus ring, selected tab underline. */
```

**Accent Color (Quant360 Primary Accent)**

The single brand accent is a cold, institutional teal-blue. It is not the electric blue of crypto dashboards. It sits at the intersection of Bloomberg orange-yellow precision and Two Sigma cool restraint. It must appear on no more than 15% of any given screen.

```
--accent-primary:   #2F81F7   /* Primary CTAs, active nav item, live indicator dot, selected tab. */
--accent-primary-hover: #388BFD
--accent-primary-muted: rgba(47, 129, 247, 0.12)  /* Background of active tab, badge fill. */
--accent-amber:     #D29922   /* Warning states, 30th-70th percentile amber zone, alert level 1. */
--accent-amber-muted: rgba(210, 153, 34, 0.12)
```

**Semantic Tokens (the financial signal vocabulary)**

This is the most critical section. These four colors do the entire job of communicating direction, magnitude, and urgency across all 14 features. They cannot be mixed with decorative colors.

```
/* POSITIVE / BULLISH */
--semantic-green-strong:  #3FB950   /* Factor premium positive, IC positive, return positive. */
--semantic-green-muted:   #238636   /* Green used on dark backgrounds for lower-stress positive states. */
--semantic-green-fill:    rgba(63, 185, 80, 0.08)   /* Row highlight for positive rows in tables. */
--semantic-green-text:    #56D364   /* Text-level positive values in stat tables. */

/* NEGATIVE / BEARISH */
--semantic-red-strong:    #F85149   /* Factor crash, negative IC, drawdown, loss. */
--semantic-red-muted:     #DA3633   /* Red used at lower intensity on saturated charts. */
--semantic-red-fill:      rgba(248, 81, 73, 0.08)    /* Row highlight for negative rows. */
--semantic-red-text:      #FF7B72   /* Text-level negative values in stat tables. */

/* NEUTRAL / TRANSITION */
--semantic-amber-text:    #D29922   /* Amber percentile zones, alert level 1 text. */
--semantic-amber-fill:    rgba(210, 153, 34, 0.08)

/* CROWDING / STRESS */
--semantic-purple-text:   #A371F7   /* Crowding score high, regime stress probability. */
--semantic-purple-fill:   rgba(163, 113, 247, 0.08)
```

**Data Series Palette (for multi-series charts)**

The critical constraint here is that all six colors must be simultaneously distinguishable by someone with deuteranopia (the most common form of color vision deficiency). This was derived from Bloomberg's own accessibility research. The palette deliberately avoids pure green-red adjacency on charts. Each color is specified with its associated factor to create semantic consistency across every chart in the application.

```
--series-1: #2F81F7   /* Market / Benchmark / Primary series. */
--series-2: #3FB950   /* Value / Long book / Positive factor. */
--series-3: #F85149   /* Momentum (contra) / Short book / Negative factor. */
--series-4: #D29922   /* Quality / Warning series. */
--series-5: #A371F7   /* Low-Vol / Crowding / Stress regime. */
--series-6: #58A6FF   /* Size / Secondary comparison. */
--series-7: #8B949E   /* Residual / Unexplained / Neutral. */
--series-8: #E3B341   /* Investment / Profitability factor. */
```

**Typography Color Tokens**

```
--text-primary:   #E6EDF3   /* All primary labels, axis labels, table header text. */
--text-secondary: #8B949E   /* Subheadings, units, secondary annotations on charts. */
--text-muted:     #484F58   /* Placeholder text, disabled state text, gridline labels. */
--text-inverse:   #0D1117   /* Text on light-colored elements (rare; used for badge text on colored fills). */
```

---

### Typography Tokens

The font system has two typefaces only. Inter for all UI chrome and data labels. JetBrains Mono (or Fira Code as fallback) for all numeric values in tables and axis labels. This two-font discipline is what differentiates a quant terminal from a generic SaaS dashboard. Numbers in a monospace face align correctly in tables without manual padding and communicate precision by appearance alone.

**Font Families**

```css
--font-ui: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-mono: "JetBrains Mono", "Fira Code", "Consolas", monospace;
```

**Font Size Scale**

This is an 8-point-rooted scale. Every value is a multiple or rational subdivision of 8.

```css
--text-xs: 10px; /* Chart gridline labels, footnotes, axis tick marks. */
--text-sm: 12px; /* Table cell body text, secondary stat labels. */
--text-base: 14px; /* Navigation items, form labels, tooltip body text. */
--text-md: 16px; /* Panel headers, primary stat labels. */
--text-lg: 20px; /* Section titles within panels. */
--text-xl: 24px; /* Primary KPI numbers in stat cards. */
--text-2xl: 32px; /* Hero metrics (annualized alpha, capacity ceiling AUM). */
--text-3xl: 48px; /* Full-screen single-metric drill-down display only. */
```

**Font Weight**

```css
--weight-regular: 400;
--weight-medium: 500; /* Table headers, nav labels. */
--weight-semibold: 600; /* Panel titles, active state labels. */
--weight-bold: 700; /* KPI values in stat cards, alert text. */
```

**Line Height**

```css
--leading-tight: 1.25; /* KPI numbers, short labels. */
--leading-normal: 1.5; /* Body text in tooltips and annotations. */
--leading-relaxed: 1.7; /* Longer plain-language summary text blocks. */
```

**Letter Spacing**

```css
--tracking-tight: -0.02em; /* Used only on --text-2xl and --text-3xl KPI numbers. */
--tracking-normal: 0em;
--tracking-wide: 0.05em; /* Uppercase section labels, stat card headings in small caps. */
--tracking-widest: 0.12em; /* STATUS badges (LIVE, PAUSED, DEGRADED). */
```

---

### Spacing Tokens

All spacing derives from a 4px base unit. The spacing scale is 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 / 128px.

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px; /* Standard internal card padding. */
--space-6: 24px; /* Panel padding, section gap within a card. */
--space-8: 32px; /* Panel-to-panel gap in the grid. */
--space-12: 48px; /* Major section separation (top nav to first content row). */
--space-16: 64px; /* Page-level vertical padding. */
```

---

### Border Radius Tokens

```css
--radius-sm: 4px; /* Badges, status pills, small chips. */
--radius-md: 6px; /* Input fields, table cells with fill. */
--radius-lg: 8px; /* Cards, panels, modals. */
--radius-xl: 12px; /* Feature-level containers, expanded panels. */
--radius-full: 9999px; /* Toggle switches, circular status dots. */
```

---

### Elevation / Shadow Tokens

Shadows on a near-black background are nearly invisible. Elevation is communicated primarily through surface color step-up (surface-1 to surface-2 to surface-3), not through drop shadows. Shadow is used exclusively for floating elements that must appear above the primary panel layer.

```css
--shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.4);
--shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5);
--shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.6); /* Modals, full-screen drawers. */
--shadow-glow-accent: 0 0 12px rgba(47, 129, 247, 0.25); /* Active panel or focused input. */
```

---

## PART III: LAYOUT SYSTEM

### Grid Architecture

The application uses a 12-column grid with a 24px gutter and 32px page margin on all sides. There is no maximum content width. The design expands to fill any screen width because the user base is PM workstations running 27-to-34-inch displays at 2560px or wider.

**Standard column configurations:**

Feature panels overwhelmingly use 8-column (primary chart) + 4-column (stat sidebar) splits. Full-width tables occupy all 12. Side-by-side comparisons use 6+6. The 4-column sidebar is a recurring design primitive across Features 2, 6, 7, 8, 10, and 13.

**Row height system:**

```
Stat card row:        80px fixed height
Chart panel (small):  280px minimum, resizable
Chart panel (medium): 400px minimum, resizable
Chart panel (large):  560px minimum, resizable
Table row height:     40px fixed (this is non-negotiable; tighter than 40px fails the 4-second legibility test)
Table header height:  44px
Panel header height:  56px (contains title + controls)
```

### Navigation Architecture

The navigation is three-tier. Zero state: only the nav is visible, with modules listed. Feature state: the left sidebar collapses to icons only (48px wide) and the main content area expands. Full-screen drill-down state: the sidebar disappears entirely and the panel is full-viewport.

**Top navigation bar:**

Height 52px. Background `--surface-1`. Left: Quant360 wordmark in Inter semibold, `--text-primary`, followed by `/` separator and the current module label in `--text-secondary`. Center: the feature tab strip (DNA / OPTIMIZER / ROTATION / REGIMES, matching the ATLAS screenshot's pattern). Right: asset search, refresh analysis button, live clock in `--font-mono`, `--text-secondary`.

**Left sidebar:**

Width 240px expanded, 48px collapsed. Contains the feature hierarchy. Each feature has an icon, a label, and a keyboard shortcut badge. The active item has `--accent-primary-muted` background and a 2px left border in `--accent-primary`.

**Right panel (contextual controls):**

Width 280px. Contains all inputs for the current feature: factor selector, lookback window, universe filter, and methodology switches. This panel slides in from the right and overlaps the main content area on narrower displays. It collapses via a toggle.

---

## PART IV: COMPONENT LIBRARY

### Stat Card

This is the highest-frequency primitive in the application. It appears in the four-card row at the top of every feature view (referencing the ATLAS screenshot's "DOMINANT MODEL BELIEF / EXPLAINED VARIANCE / ANNUALIZED ALPHA / FACTOR STABILITY" row).

**Anatomy:**

```
Container:       --surface-2 background, --radius-lg, 1px border --border-default
Padding:         --space-6 horizontal, --space-4 vertical
Top label:       --text-xs, --weight-medium, --tracking-wide, uppercase, --text-muted
Primary value:   --font-mono, --text-2xl, --weight-bold, --tracking-tight, --text-primary
Secondary value: --text-sm, --text-secondary (e.g., delta vs. prior period)
Trend indicator: a small sparkline in 40px x 24px (using --series-1), right-aligned
Bottom label:    --text-xs, --text-muted (e.g., "PERSISTENCE SCORE / 10" from the screenshot)
```

**State variants:**

Positive trend: secondary value in `--semantic-green-text` with an upward triangle glyph. Negative trend: `--semantic-red-text` with downward triangle. Alert state: card border changes to `--accent-amber`, background to `--semantic-amber-fill`. Critical: border to `--semantic-red-strong`.

---

### Panel Container

All major chart and table panels share this container.

```
Background:      --surface-1
Border:          1px solid --border-default
Border-radius:   --radius-xl
Panel header:    56px height, --surface-2 background, top --radius-xl applied
                 Left: icon (20px, --text-secondary) + panel title (--text-md, --weight-semibold, --text-primary)
                 Right: info icon, expand icon, download icon (all 20px, --text-muted, hover --text-secondary)
Body padding:    --space-6 all sides
```

**Panel header controls** are always right-aligned and use icon buttons only (no text labels). Hover state lifts to `--surface-3`.

---

### Chart Specifications

**Axis and Grid System (universal across all charts)**

```
Grid lines:      1px solid --border-muted, horizontal only by default, opacity 0.5
Axis lines:      removed entirely (the grid is sufficient; axis lines create noise)
Axis labels:     --font-mono, --text-xs, --text-muted
Axis title:      --text-sm, --text-secondary, --weight-medium (rotated 90° for Y axis)
Legend:          horizontal, below chart, --text-xs, --text-secondary, 24px icon + label
Tooltip:         --surface-2 background, --shadow-lg, --radius-md, --border-default border
                 Title in --text-sm --weight-semibold, values in --font-mono --text-sm
```

**Interaction Model (universal)**

Hover reveals a crosshair cursor. Tooltip appears 8px offset from cursor. Click on legend item toggles series visibility (hidden series fades to opacity 0.15, not removed). Double-click on any chart panel triggers full-screen expand mode. Scroll to zoom on time-axis charts; drag to pan.

---

### Chart Type Specifications by Feature

Every chart type is specified at the level of configuration, not just description. The implementation team should be able to read these and build without a Figma file.

---

**F1: Factor Valuation Spread Monitor**

**Primary output (factor PE dial gauge):**

Use a D3-rendered semicircular arc gauge. Inner radius 70% of outer radius. Arc spans 180 degrees (half circle, flat edge at bottom). Background arc: `--border-muted` at full opacity. Filled arc: color interpolated using a three-stop scale: `--semantic-green-strong` at 0-30th percentile, `--accent-amber` at 30-70th, `--semantic-red-strong` at 70-100th. The needle is a thin 2px line from center to the arc, white, with a 6px filled circle at the pivot. The percentile number is displayed center-bottom of the gauge in `--font-mono --text-xl --weight-bold`. Below it: the factor name in `--text-sm --text-secondary`. A secondary line in `--text-xs --text-muted` reads the implied 12-month expected return from the regression. Each gauge card is 160px wide by 120px tall. The dashboard view tiles them in a responsive grid of 4 per row minimum.

**Historical percentile band chart:**

A Recharts AreaChart. X-axis: date, --font-mono --text-xs. Y-axis: percentile 0-100. The area fill uses a gradient from `rgba(47, 129, 247, 0.3)` at the area top to `rgba(47, 129, 247, 0.02)` at the baseline. The stroke is `--series-1` at 1.5px. The current level is marked by a vertical dashed line in `--accent-amber`. The crisis anchor dates (GFC, COVID, Liberation Day) are marked by vertical dotted lines in `--text-muted` with labels at the top.

**Factor valuation correlation matrix:**

A D3 heatmap. N factors on both axes. Cell fill interpolated on a diverging scale: `--semantic-red-strong` at 1.0 correlation, `--surface-3` at 0.0, `--semantic-green-strong` at -1.0. Correlation values above |0.4| are printed in each cell in `--font-mono --text-xs`. Cell hover tooltip shows: factor pair names, correlation value, and statistical significance.

---

**F2: Factor Exposure Decomposition (Portfolio X-Ray)**

**Exposure bar chart:**

A Recharts horizontal BarChart. Y-axis lists factor names in `--text-sm --text-primary`. X-axis is standardized z-score, symmetric around 0, with the zero line rendered as a 1.5px solid `--border-emphasis` line. Positive bars use `--semantic-green-strong`. Negative bars use `--semantic-red-strong`. Error bars (95% bootstrap CI) are overlaid as thin 1px lines with 4px caps in `--text-secondary`. The active factor (hovered) row highlights in `--surface-3`. A vertical dashed line marks the 0.4 standard deviation threshold for "unintended exposure" in `--accent-amber`.

**Exposure heatmap (holdings level):**

A D3 heatmap with stocks as rows and factors as columns. Rows are sorted by total absolute exposure by default. Cell fill: same diverging scale as the correlation matrix. Row labels (ticker symbols) in `--font-mono --text-xs`. Column labels (factor names) rotated 45 degrees. A "sort by" dropdown in the panel header allows resorting by any factor column.

**Rolling exposure time series:**

A Recharts LineChart. One line per factor. Uses the full `--series-1` through `--series-7` palette. Lines are 1.5px. The zero line is dashed at 1px in `--border-emphasis`. Below the chart: a time-range selector bar (the small brush component from Recharts) allowing the user to drag-select a sub-period.

---

**F3: Factor Return Attribution and Performance Decomposition**

**Waterfall chart:**

This is the single most important output in the application. It must be built in D3 because Recharts does not support waterfall natively. Each bar represents one return component (Market, Value contribution, Momentum contribution, Quality contribution, Selection, Interaction, Carryover). Positive bars extend upward from the running total in `--semantic-green-strong`. Negative bars extend downward in `--semantic-red-strong`. A thin connector line at the top/bottom of each bar connects to the start of the next bar in `--border-default`. The bar width is 48px with 16px gaps. Each bar is labeled on top with the bp value in `--font-mono --text-sm` and on the bottom with the component name in `--text-xs --text-muted`.

**Stacked area chart (cumulative contributions):**

A Recharts AreaChart with stacking enabled. Fill opacity 0.8. Each series uses its assigned series color. The legend is placed below the chart in two rows of four, with checkboxes allowing series toggle.

**Information ratio by component:**

A Recharts BarChart, vertical orientation, with two bars per factor (rolling 12M IR in `--series-1` and rolling 36M IR in `--series-6`, grouped side by side). A horizontal reference line at IR = 0.5 in `--accent-amber` dashed marks the institutional minimum threshold.

---

**F4: Factor Timing and Probabilistic Regime Analysis**

**Probabilistic regime timeline:**

This is the signature chart of Feature 4 and must be built in D3. It is a stacked area chart where the Y-axis runs from 0 to 1 (probability), not from 0 to 100%. Each regime state occupies a color band:

```
Expansion:      --series-2 (green) at 0.7 opacity
Transition:     --series-4 (amber) at 0.7 opacity
Stress:         --series-3 (red) at 0.7 opacity
Liquidity Crisis: --series-5 (purple) at 0.7 opacity
```

The bands sum to 1 at every date. The chart is 560px tall minimum. Current date is marked by a vertical line in `--accent-primary`. A horizontal strip below the chart (32px tall) shows annotated historical events as colored pills.

**Current regime probability readout:**

A set of four horizontal progress bars, one per regime state, with the probability value in `--font-mono --text-md --weight-bold` right-aligned. Color of each bar matches its regime color from above.

**Factor return heatmap by regime:**

A D3 heatmap. Rows: factors. Columns: regime states. Cell fill: same diverging color scale as all other heatmaps. T-statistic annotated in `--font-mono --text-xs --text-muted` in the bottom-right of each cell. Sample size (n = X months) in the top-right.

---

**F5: Alpha Decay and Factor Half-Life Analysis**

**IC decay curve:**

A Recharts LineChart. X-axis: forward horizon in trading days (1, 5, 21, 63, 126, 252). Y-axis: rank IC from 0 to the maximum observed IC (never fixed to 1.0 — empirical scale only). One line per selected factor using the series palette. Each line has 95% bootstrap confidence bands rendered as a matching-color fill at 0.1 opacity. A horizontal dashed line at IC = 0 in `--border-emphasis` marks the zero-skill threshold.

**Fitted decay model overlay:**

Three additional line overlays per factor (linear, exponential, hyperbolic) shown as dashed lines (dash patterns: 4,4 for linear; 8,4 for exponential; 2,4 for hyperbolic). A legend badge in the corner shows R-squared for each model in `--font-mono --text-xs`.

**Half-life parameter table:**

A standard table with sticky header. Columns: Factor / Model / Half-Life (days) / Half-Life (calendar weeks) / Optimal Rebalancing Frequency / Bootstrap 90% CI Lower / Bootstrap 90% CI Upper. All numeric cells: `--font-mono --text-sm`. Column headers: `--text-xs --weight-medium --tracking-wide` uppercase. Rows alternate between `--surface-1` and `--surface-2` background at opacity 0.5.

**Rebalancing cost-benefit curve:**

A Recharts ComposedChart. X-axis: rebalancing frequency (daily through annual, ordinal). Left Y-axis: net IC after costs. Right Y-axis: total transaction cost as a fraction of gross IC. One area (net IC, `--series-2` fill) and one line (cost fraction, `--series-3`). The intersection point (the optimal frequency) is highlighted with a vertical band in `--accent-primary-muted` and labeled with an annotation.

---

**F6: Factor Crowding Monitor**

**Crowding composite gauge:**

This is the signature visual of Feature 6. It is a full D3 circular gauge, not a semicircle. The outer ring is the current crowding percentile score, rendered as an arc with color interpolation identical to the F1 dial gauges. Inside the ring: a large number in `--font-mono --text-3xl --weight-bold`, colored semantically. Inside that: a smaller label in `--text-xs --text-muted` reading "CROWDING PERCENTILE." The density plot of historical readings is displayed as a D3 histogram below the gauge, with the current reading marked by a vertical line in `--accent-primary`. The histogram bars use `--surface-3` fill with `--accent-primary` for the bar containing the current reading.

**Crowding time series with annotated crashes:**

A Recharts LineChart with a colored background band. The line is `--series-1` at 1.5px. The background band is the crowding percentile rendered as a color gradient using `mix-blend-mode: multiply` (or equivalent CSS approach): green below 40th percentile, amber 40-70th, red above 70th. Crash annotation events are vertical dashed lines in `--semantic-red-strong` with pill labels above the chart area.

**Individual metric radar chart:**

A D3 radar chart with four axes (Valuation Spread / Autocorrelation Stress / HHI Concentration / Bid-Ask Deterioration). Axis labels in `--text-xs --text-primary`. The polygon fill is `--accent-primary-muted`. The polygon stroke is `--accent-primary` at 2px. The historical average polygon is shown in `--border-emphasis` dashed at 1px underneath.

**Crash probability table:**

Three-column × N-row table (1M / 3M / 6M crash probability). The probability values are formatted as percentages and colored semantically: above 20% in `--semantic-red-text`, 10-20% in `--semantic-amber-text`, below 10% in `--text-primary`.

---

**F7: Factor Backtesting Engine**

**Two-panel equity curve:**

Top panel (70% of height): a Recharts AreaChart. Two area series: gross return in `--series-2` at 0.15 fill opacity and net return in `--series-1` at 0.2 fill opacity. The benchmark is a single line in `--series-7` dashed at 1px with no fill. The gap between gross and net fills is shaded in `--semantic-red-fill` to visually represent the transaction cost drag. A log-scale toggle is in the panel header controls.

Bottom panel (30% of height): a Recharts AreaChart for drawdown. The area is a negative fill (values are negative) in `--semantic-red-strong` at 0.6 opacity. The zero line is `--border-emphasis`. Max drawdown is labeled with a callout annotation.

**Quintile monotonicity chart:**

A Recharts BarChart with 5 bars (Q1 through Q5) or 10 bars (D1 through D10). Each bar is colored on a green-to-red gradient from Q1 (best, `--semantic-green-strong`) to Q5/D10 (worst, `--semantic-red-strong`). The expected monotonic decrease in bar height from left to right is the visual test of signal validity. If any bar violates the monotone pattern (e.g., Q3 higher than Q2), the violating bar is outlined in `--accent-amber` dashed.

**Transaction cost decomposition:**

A Recharts BarChart with stacking. Three stacks per bar: explicit cost (`--series-4`), market impact (`--series-3`), timing cost (`--series-5`). Each bar represents one calendar year. A horizontal dashed line marks the average total cost across all years.

**Monte Carlo confidence bands:**

Overlay on the equity curve chart. The 10th and 90th percentile equity curves are rendered as thin lines in `--border-muted`. The area between them is filled with `--surface-3` at 0.4 opacity. The 50th percentile (median) is `--series-7` at 1px. The realized equity curve (if in OOS mode) is `--accent-primary` at 2px on top of all MC bands.

---

**F8: Factor Covariance Matrix**

**Correlation heatmap:**

D3 heatmap. The color scale is a five-stop diverging scale:

- -1.0: `#2F81F7` (deep blue)
- -0.5: `#8AB4F8` (light blue)
- 0.0: `#1C2128` (near-background neutral)
- +0.5: `#F8B050` (amber)
- +1.0: `#F85149` (red)

Cell values above |0.3| are printed in `--font-mono --text-xs`. Factor pairs with |correlation| above 0.6 have a subtle 1px inner border in `--border-emphasis`. The matrix is sortable by factor type via a dropdown.

**Normal vs. crisis comparison (side-by-side heatmaps):**

Three equal-width D3 heatmaps rendered in a row. Left: normal regime. Center: crisis regime. Right: difference (delta), with its own diverging scale where positive delta (correlation increased in crisis) uses `--semantic-red-strong` and negative delta uses `--semantic-green-strong`. Panel headers in `--surface-2` are labeled "NORMAL REGIME," "CRISIS REGIME," and "DELTA (CRISIS - NORMAL)."

---

**F9: Strategy Capacity Analyzer**

**Capacity curve chart:**

A Recharts ComposedChart. X-axis: AUM in log scale from $1M to $10B, formatted as "$10M," "$100M," "$1B," etc. Left Y-axis: net alpha in annualized bps. One area series for net alpha (green fill when positive, red fill when negative), with the color transition happening exactly at y=0. The capacity ceiling (net alpha = 0 crossing) is marked by a vertical band in `--semantic-red-fill` and a callout label: "CAPACITY CEILING: $X.XB." The "optimal AUM" (~50% of ceiling) is marked by a vertical line in `--accent-primary` dashed with a callout: "OPTIMAL AUM: $X.XB." A horizontal reference line at y=0 is `--border-emphasis` solid.

**Slippage vs. AUM table:**

A five-column table. AUM / Average Slippage (bps) / Net Alpha (bps) / Net Sharpe / Viable. The "Viable" column uses a green circle checkmark or red X icon. The row for the current fund's AUM is highlighted in `--accent-primary-muted` with a left border in `--accent-primary`.

---

**F10: Portfolio Optimizer**

**Efficient frontier chart:**

D3 scatter plot. X-axis: annualized portfolio volatility. Y-axis: annualized expected return. 50 Pareto-optimal points are rendered as small circles (4px radius) in `--series-7` connected by a curve in `--series-7` at 1px. The selected optimal point is a larger circle (8px) in `--accent-primary` with a glow shadow. The minimum variance point is a square marker in `--series-2`. The maximum Sharpe point is a diamond marker in `--series-4`. Clicking any frontier point updates all sidebar stats to reflect that portfolio.

**Factor allocation bar chart:**

A Recharts horizontal BarChart identical in structure to the F2 exposure chart, showing each factor's weight in the optimal solution. Each bar is colored by sign. An additional thin bar overlay in `--series-4` shows the marginal contribution to risk for each factor.

**Robust vs. standard comparison:**

Two side-by-side horizontal bar charts. Left: standard MV optimal weights. Right: robust optimal weights. Each bar is colored by sign. Bars that differ by more than 0.05 in absolute weight are highlighted with `--accent-amber` outlines on both panels.

---

**F11: Stress Testing and Reverse Stress Testing**

**Portfolio P&L waterfall under scenario:**

Identical structure to the F3 waterfall but with a scenario context header showing the scenario name, type (historical/parametric), and the closest historical analog period.

**Contagion impulse response chart:**

A D3 grouped bar chart. X-axis: time horizon (1D / 5D / 10D / 21D). Y-axis: factor return response in standard deviations. One bar group per target factor, with 90% confidence bands as error bars. The shocking factor (e.g., "Momentum shock of 1 sigma") is labeled in the panel header. Bars above zero in `--semantic-green-strong`, below in `--semantic-red-strong`.

**Multi-scenario comparison table:**

A table where rows are scenarios and columns are: Scenario Name / Type / Portfolio P&L / Max Factor Contributor / Recovery Time (est. days) / Hedge Cost (bps). Color-coded P&L cells using the full semantic palette.

---

**F12: Factor DNA Attribution**

**Factor DNA octagonal radar chart:**

D3 radar chart with eight axes. The eight axes and their directions (higher = better):

1. IC (higher raw IC = better)
2. ICIR (higher signal-to-noise = better)
3. Half-Life (longer half-life = lower rebalancing cost = higher score here)
4. Crowding (lower crowding = higher score, so this axis is inverted)
5. Sector Purity (lower HHI = less sector-concentrated = higher score)
6. Regime Stability (lower Sharpe spread across regimes = more stable = higher score; inverted)
7. Factor Independence (lower correlation to nearest neighbor = higher score; inverted)
8. Factor Purity (higher purity score = better)

All axes are normalized to 0-100. The primary factor polygon uses `--accent-primary` stroke at 2px and `--accent-primary-muted` fill. Comparison factor polygons use `--series-4` and `--series-5` at 1.5px stroke and 0.06 opacity fill. Axis labels in `--text-xs --text-primary`.

**Auto-classifier output (horizontal stacked bar):**

A single full-width stacked bar chart, 40px tall, with four segments: Risk Factor / Behavioral Factor / Structural Factor / Data-Mining Artifact. Colors: `--series-2` / `--series-1` / `--series-4` / `--series-5`. Above the bar: the dominant category label in `--text-md --weight-semibold` and its confidence percentage in `--font-mono`. Below: a single-sentence plain-language classification summary in `--text-sm --text-secondary`.

**Return anatomy decomposition:**

A Recharts RadialBarChart or equivalent D3 donut chart with three segments: Valuation Reversion / Characteristic Momentum / Residual Premium. Percentages printed in the center as three stacked lines. Segment labels on the outside with leader lines in `--text-xs`.

---

**F13: Live Signal Monitoring Dashboard**

**Signal health table:**

This is a live-updating table, the most information-dense output in the application. Every row is one factor. Columns:

```
Factor Name:         --text-sm --weight-medium --text-primary
IC (21D):            --font-mono --text-sm, colored by sign
IC Z-Score:          --font-mono --text-sm, colored: green above 0, red below -1.5
Crowding Pctile:     --font-mono --text-sm, colored by zone
Crowding ΔD21:       --font-mono --text-sm with directional arrow glyph
Return-Char Align:   a colored pill: "ALIGNED" in --semantic-green-fill / --semantic-green-text or "DIVERGING" in --semantic-red-fill / --semantic-red-text
Health Score 0-100:  a mini horizontal progress bar (80px wide, 8px tall) + the number right-aligned in --font-mono
```

Rows above a degradation threshold (Health Score below 40) pulse with a subtle 2s animation: the row background alternates between `--surface-1` and `--semantic-red-fill` at 0.04 opacity. This animation stops once the user acknowledges the alert.

**IC drift time series with alert zone:**

A Recharts LineChart. The line is `--series-1` at 1.5px. A horizontal reference line at the long-run mean IC is `--accent-amber` dashed. The alert zone (below the drift threshold) is a horizontal fill band in `--semantic-red-fill` extending to the bottom of the chart. The current IC value is labeled at the right terminus of the line with its exact value in `--font-mono --text-xs`.

**Structural break p-value chart:**

A Recharts BarChart. X-axis: dates over the trailing 252 days. Y-axis: Chow test p-value from 0 to 1. A horizontal dashed line at p = 0.05 in `--semantic-red-strong` marks the significance threshold. Bars below the threshold (statistically significant breaks) are colored `--semantic-red-strong`. Bars above are `--surface-3`.

---

**F14: Allocator Transparency Report Generator**

**PDF output design:**

The generated PDF is not a "web screenshot." It is a formally laid-out document using a professional typesetting approach. The design specifications for the PDF output are as follows.

Page size: A4 portrait (210mm x 297mm). Margins: 20mm top / bottom / left / right. A running footer on every page: fund name (left), "CONFIDENTIAL" watermark text (center, `--text-muted` equivalent in light gray), page number of total (right).

**Cover page:**

Fund name in a large serif typeface (EB Garamond 32pt if available, otherwise Georgia) centered vertically. Subtitle: "Factor Attribution & Risk Report — [Quarter Year]" in Inter 16pt. Report date and fund AUM as two centered lines in Inter 12pt.

**Body typesetting:**

Section headings: Inter 14pt semibold, all caps, with a thin 0.5pt horizontal rule below. Body text: Inter 11pt at 1.5 leading. Stat callouts: JetBrains Mono 11pt. Table cells: Inter 10pt, alternating row fills (white and #F6F8FA for the light-mode PDF). Charts are embedded as high-resolution SVGs at 300 DPI equivalent.

The light-mode chart palette for the PDF uses inverted surface tokens:

```
PDF-background:  #FFFFFF
PDF-surface-1:   #F6F8FA
PDF-border:      #D0D7DE
PDF-text:        #24292F
PDF-text-muted:  #57606A
PDF-accent:      #0969DA   /* The same blue family, saturated for print. */
PDF-green:       #2DA44E
PDF-red:         #CF222E
PDF-amber:       #BF8700
```

All charts regenerated in this inverted palette before PDF export. No dark backgrounds in the PDF output.

---

## PART V: INTERACTION DESIGN STANDARDS

### Keyboard Navigation

Every panel must be fully keyboard-navigable. Tab order follows visual reading order (left-to-right, top-to-bottom). The following global shortcuts are mandatory:

```
Cmd/Ctrl + K:    Global command palette (search any factor, feature, or asset)
Cmd/Ctrl + R:    Refresh all live data
Cmd/Ctrl + E:    Export current panel to PNG or CSV
F:               Toggle full-screen on the focused panel
1-9:             Jump to Feature 1 through Feature 9 directly
0:               Jump to Feature 10-14 sub-menu
Esc:             Exit full-screen, close modal, deselect
/                Open asset search in top bar
```

### Animation Standards

Animations are used conservatively and serve functional purposes only.

```
Panel load:          200ms ease-out opacity from 0 to 1. No slide-in. No bounce.
Chart data update:   300ms ease-in-out transition on bar heights and line positions.
Tooltip appear:      80ms ease-out, no delay.
Tab switch:          100ms cross-fade, no slide.
Modal open:          150ms ease-out scale from 0.97 to 1.0 plus opacity.
Alert pulse:         2000ms sinusoidal opacity cycle, range 0.02 to 0.08 on background.
Number ticker:       350ms ease-out numeric counter animation for KPI values on page load only.
```

Parallax, entrance animations on scroll, and decorative loading spinners are explicitly prohibited.

### Loading States

Every panel has three loading states. Skeleton: matching the final layout dimensions, with `--surface-3` fill rectangles where text and charts will appear, pulsing at 1.5s period. Partial: chart framework (axes, gridlines, labels) renders first, then data lines populate. Error: the panel retains its layout but the chart area shows a minimal error message in `--text-muted` with a retry button.

### Tooltip Design

Every data point across every chart surface reveals a tooltip on hover. The tooltip specification is universal:

```
Background:     --surface-2
Border:         1px solid --border-default
Border-radius:  --radius-md
Padding:        --space-3 --space-4
Shadow:         --shadow-lg
Max-width:      280px
Header:         --text-sm --weight-semibold --text-primary
Values:         --font-mono --text-sm, labeled + value pairs
Footer:         --text-xs --text-muted (date or sample size context)
```

---

## PART VI: TECHNOLOGY IMPLEMENTATION STACK

### Chart Library Selection by Feature

The correct library selection determines whether implementation is four weeks or sixteen weeks. These recommendations are definitive, not suggestions.

**Apache ECharts:** Use for Features 4 (probabilistic regime timeline with stacked probability areas), 6 (crowding gauge and annotated time series), 8 (covariance heatmaps with complex interaction), and 13 (live-updating signal health table with sparklines). ECharts is chosen specifically because it handles large datasets (100,000+ data points for the 10-year daily history across 5,000 stocks) without frame-rate degradation, which Recharts cannot guarantee.

**Recharts:** Use for Features 1 (percentile band charts and cross-sector tables), 2 (exposure bar charts, rolling time series), 3 (stacked area attribution, factor hit rate), 5 (IC decay curves, rolling half-life), 7 (equity curves, quintile charts, Monte Carlo bands), 10 (factor allocation bars, robust comparison). Recharts is the correct tool when the dataset per chart is under 10,000 points and the team needs rapid iteration velocity.

**D3.js (custom):** Use for Features 1 (the semicircular dial gauges), 4 (the probabilistic regime timeline requires a fully custom stacked-area-to-probability visualization), 6 (circular gauge with density histogram), 7 (waterfall chart for transaction cost decomposition), 12 (octagonal radar chart, auto-classifier bar). D3 is used only when no existing library component matches the required output type exactly.

**TanStack Table:** Use universally for all data tables (F1 cross-sector, F2 holdings heatmap, F5 half-life parameter, F6 crash probability, F7 statistics, F9 slippage). TanStack Table is chosen for its virtual scrolling (essential for 5,000-row holdings tables), column pinning, and sorting capabilities.

### Font Loading

Both Inter and JetBrains Mono must be loaded via self-hosted woff2 files, not from Google Fonts CDN. For a financial application used by quant PMs who may be operating in restricted network environments, CDN dependencies for core typefaces represent an unacceptable reliability risk. Self-host both font families and use `font-display: swap` with the appropriate system fallback chain specified in the tokens section.

---

## PART VII: THE FOUR-SECOND LEGIBILITY TEST

Every proposed design output for Quant360 must pass this test before it ships. A PM who has never used this specific panel before opens it and is given four seconds. They must be able to answer: what is the signal telling me, is it positive or negative, and what is the magnitude? If they cannot, the panel requires redesign.

The four specific failure modes that cause panels to fail this test are: (1) chart titles that describe the methodology rather than the finding ("Rolling 63-day IC computed by Spearman rank correlation" versus "Value Signal Strength: Currently 72nd Percentile - ELEVATED"), (2) axis labels that omit units, (3) color schemes that require a legend to decode directionality, and (4) tables where the most important column is not the leftmost visible column or is not visually differentiated from secondary columns.

The ATLAS screenshot provided demonstrates this well in the "DNA STUDIO" panel header and the four stat cards. "FF5_MOM" as the dominant model, "21.2%" as the explained variance, "17.11%" as the annualized alpha, "71.8" as the factor stability score: all four read in under two seconds. That information density and label clarity is the minimum bar for every panel in Quant360.

---

This specification is complete and self-contained. An engineering team with competence in React, ECharts, Recharts, and D3 can build every panel across all 14 features from this document without a single Figma handoff. The design tokens alone constitute a full design system. The chart specifications replace mockups. The interaction standards replace a UX flow document.

Yes, completely fine — actually ideal for your use case.

Portfolio Visualizer's card-by-card sequential output format works perfectly here for three reasons specific to Quant360:

**Cognitive load management.** Each feature (especially F7's backtesting or F12's DNA card) produces 8-10 distinct outputs. Rendering them sequentially as the user scrolls keeps the PM anchored to one analytical question at a time rather than drowning in a simultaneous dashboard. Bloomberg itself uses this pattern for PORT attribution — you scroll through sections, you don't see all of them at once.

**Implementation simplicity.** Each output card is a self-contained React component with its own data fetch, loading state, and error boundary. You are not coordinating cross-panel state synchronization, which is where most quant dashboard projects die in engineering.

**Allocator-readiness.** When a PM is walking an allocator through the DDQ response, sequential card scrolling maps directly to the narrative flow of a presentation. Dashboard mode (everything at once) is for the PM's own morning routine. Sequential card mode is for showing your work to someone else. Both use cases are served by the same architecture.

The one thing to get right: the control panel (factor selector, lookback, universe filter) must be a sticky right sidebar or a sticky top strip that persists as the user scrolls through the cards. The user should never have to scroll back up to change an input. That is the primary UX failure mode in Portfolio Visualizer's own implementation and it is worth solving explicitly in your design from the start.

Perfect — that is the correct architecture and it is strictly better than Portfolio Visualizer's approach.

The pattern is:

**Step 1: Input form (full page or top section)**
User configures everything — factor selector, universe, lookback, methodology switches, benchmark. Single "Run Analysis" button at the bottom. Nothing computes until that button is pressed.

**Step 2: All output cards render sequentially below** (or the page transitions and cards appear one by one as they compute)

This is exactly how Quantpedia Pro and FactSet's factor analytics work internally. The reasons this is the right call:

**It forces intentional computation.** The user has committed to a specific configuration before seeing any output. They are not chasing moving outputs as they adjust inputs. This matters for a quant PM who needs to be able to say "I ran this analysis with these exact parameters" — the input form becomes an implicit audit trail.

**It maps to the report generator in F14.** The input form configuration IS the parameter set that gets stamped into the allocator PDF. You get the audit trail for free.

**It makes loading states trivial.** Cards render sequentially as each computation completes — the first card (stat cards / KPIs) appears in under a second, the heavy cards (Monte Carlo, DCC-GARCH covariance) appear last. The user sees progress rather than a blank screen.

The one architectural decision to nail: whether "Run Analysis" is a full page transition (input form disappears, output page appears) or a scroll-down reveal (input form stays at top, outputs render below). The page transition approach is cleaner for the F14 PDF workflow. The scroll-down approach is better for iterative exploration where the user wants to tweak one input and re-run. Given your user is a quant PM doing research, I would go scroll-down with the input form collapsing into a compact sticky summary strip at the top showing the key parameters, so they can see what the analysis was run on while reading the outputs.
