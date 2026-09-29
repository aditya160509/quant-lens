# Factor Intelligence Module: Frontend Pending Implementation Tasks

This document tracks the missing frontend features and visual components required to meet the **Quant360 Design Specification** (`factors design.md`).

---

## 1. Advanced Visual Engine Implementation
The current implementation uses Recharts as a placeholder. The specification mandates high-performance and custom D3 visuals for professional institutional usage.

### D3.js Custom Components (Missing)
- [ ] **F1: Semicircular Arc Gauges**: 180-degree flat-bottom gauges with interpolated color scales (Green-Amber-Red) and needle-pivot logic.
- [ ] **F1: Crisis Anchor Lines**: Vertical dotted lines for GFC/COVID/Liberation Day on percentile band charts.
- [ ] **F3: Institutional Waterfall Chart**: Custom D3 implementation with running total connector lines (Recharts BarChart is a temporary placeholder).
- [ ] **F4: Probabilistic Regime Timeline**: The "Signature Chart" - a specialized stacked-area-to-probability timeline.
- [ ] **F4: Annotated Historical Events Bar**: Horizontal strip below the timeline showing colored pills for macro events.
- [ ] **F5: Fitted Decay Model Overlay**: Support for 3 dash patterns (4,4 linear, 8,4 exponential, 2,4 hyperbolic) with R-squared badges.
- [ ] **F5: Rebalancing Cost-Benefit Intersection**: ComposedChart logic to highlight the intersection of net IC and cost curves.
- [ ] **F6: Circular Crowding Gauge**: Full 360-degree ring gauge integrated with a D3 density histogram.
- [ ] **F7: Two-Panel Equity Curve**: Split 70/30 layout with cost-gap shading and log-scale toggle.
- [ ] **F7: Quintile Monotonicity Diagnostic**: Specific dashed outlines for bars that violate the expected return pattern.
- [ ] **F10: Efficient Frontier D3 Scatter**: Pareto curve with "glow shadow" optimal point, square min-var marker, and diamond max-sharpe marker.
- [ ] **F12: Octagonal DNA Radar**: Custom 8-axis radar chart with normalized axes (0-100) and multi-factor polygon overlays.
- [ ] **F12: Donut Stacked Legend**: Return anatomy donut with three stacked percentage lines in the center.
- [ ] **Stat Card Sparklines**: Every KPI card (MetricDeck) requires a mini 40x24px trend sparkline using `--series-1`.

### Apache ECharts Integration (Missing)
*Required for high-data-volume features to maintain 60FPS performance.*
- [ ] **F8: Covariance Matrix Heatmaps**: Migration to ECharts for interaction with large matrices.
- [ ] **F13: Signal Health Dash**: ECharts for live-updating grids with embedded sparklines.

---

## 2. Professional Navigation & Interaction (The "Bloomberg" UX)
The interface must transition from a standard web app to a keyboard-first terminal experience.

- [ ] **Global Command Palette (Cmd/Ctrl + K)**: Interface to search assets, factors, and jump between features.
- [ ] **Mandatory Keyboard Shortcuts**:
    - `1-9`: Jump to Features.
    - `Cmd + R`: Refresh Analysis.
    - `Cmd + E`: Export Panel.
    - `F`: Toggle Full-screen focused panel.
- [ ] **Double-Click Full-screen**: Universal chart interaction to expand any panel to the full viewport.
- [ ] **Sticky Input Summary**: Collapse the "Input Form" into a thin, sticky strip at the top of the viewport when scrolling through output cards.
- [ ] **Precision Micro-Interactions**:
    - [ ] **Crosshair Cursors**: Hovering over any chart surface must reveal a crosshair.
    - [ ] **Offset Tooltips**: Tooltips must maintain a strict 8px offset from the cursor position.
    - [ ] **Series Toggling**: Legend clicks should fade other series to 0.15 opacity instead of removing them.

---

## 3. Layout & UI Polish
- [ ] **Contextual Right Panel**: Shift configuration inputs from the top `config-card` to a 280px sliding right-side drawer as specified.
- [ ] **High-Fidelity Skeletons**: Loading states must match the exact dimensions and grid layout of the final output cards (Part V).
- [ ] **Self-Hosted Typography**: Ensure `Inter` and `JetBrains Mono` are served as local `woff2` files (Part VI).
- [ ] **Annotation Persistence**: Ensure workspace notes are reliably synced to the backend (currently using local storage as a bridge).
- [ ] **Animation Timing Enforcement**:
    - [ ] Panel Load: 200ms ease-out.
    - [ ] Data Transitions: 300ms ease-in-out.
    - [ ] Tooltip Entrance: 80ms ease-out.

---

## 4. Feature-Specific Missing UI Logic
- [ ] **F14: PDF Layout Generator**: Typesetting logic to generate the "Allocator Report" with the light-mode inverted palette (Part IV).
- [ ] **F13: Alert Pulsing**: Implementation of the 2000ms sinusoidal pulse animation for degraded signal health rows.
- [ ] **F7: Drawdown Surface**: Implementation of the negative-fill area chart for max drawdown visualization.
- [ ] **F9: Net Alpha Capacity Curve**: Implementation of the log-scale AUM axis with the capacity ceiling red-fill transition.

---

- [ ] **Realtime vs. Research Mode**: UI logic to toggle feature availability based on the compute mode selected.
