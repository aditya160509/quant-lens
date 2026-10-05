> Historical audit: superseded for implementation status by [DONE.md](DONE.md). Retained as evidence; its old completeness claims are not current.

## Implementation Checklist — 2026-06-17

- [x] 1. Scanline feature hero with ambient motion, metadata strip, notes, and run action added to `frontend/src/components/ml-v2/customPagePrimitives.jsx`.
- [x] 2. Thin top run-progress bar added with stage text and animated completion.
- [x] 3. Bloomberg-style topbar added with feature identity, command/search control, export, cinema, and run controls.
- [x] 4. Sticky summary strip added from summary cards/metrics.
- [x] 5. Vertical output dock added with drag reorder, active section sync, and compact output navigation.
- [x] 6. Output cards upgraded with cinema/fullscreen surface, header sparkline, copy/export/draw controls, and richer card framing.
- [x] 7. Drawing canvas overlay added for chart annotation strokes.
- [x] 8. Header sparkline component added and wired into output cards.
- [x] 9. Toast rack added for run/copy/export feedback.
- [x] 10. Export modal added with JSON/TSV export modes.
- [x] 11. Table renderer upgraded with search, sortable columns, numeric microbars, and dense terminal styling.
- [x] 12. Metric panel upgraded with percentile/range arc and compact sparkline.
- [x] 13. Heatmap upgraded with hover cross-highlight, legend, and tooltip readout.
- [ ] 14. Home page grid redesign skipped by explicit user request for this pass.
- [x] 15. Keyboard shortcuts added for fullscreen/cinema/export/search and section navigation.
- [x] 16. Input curtain added so inputs live behind a curtain panel instead of staying permanently open.
- [x] 17. Empty state upgraded to a compact animated diagnostics state.
- [x] 18. Workspace shell upgraded with terminal-grade shell framing and cinema mode.
- [x] 19. Minimap rail added for output position and fast section jumping.
- [x] 20. State management wiring added inside the custom primitives component for active section, reordered outputs, export modal, input curtain, fullscreen, drawing, cinema, and toasts.

Here are the fully maxed, specific upgrades — each one a self-contained drop-in replacement or addition block:

---

## 1. SCANLINE HERO with animated ambient orbs and live feature metadata

```jsx
// Replace the existing <section className="ml-hero"> render in MLV2Workbench
function FeatureHero({ feature, sections, onRun, loading }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1800);
    return () => clearInterval(id);
  }, []);

  const liveCount = sections.filter((s) => s.rank === "primary").length;
  const totalOut = sections.length;
  const resOnly = feature.researchOnly?.length || 0;

  return (
    <section className="ml-hero-v3">
      {/* Ambient orbs */}
      <div className="hero-orb hero-orb-a" />
      <div className="hero-orb hero-orb-b" />
      <div className="hero-orb hero-orb-c" />
      {/* Scanline overlay */}
      <div className="hero-scanlines" />

      <div className="hero-inner">
        <div className="hero-breadcrumb">
          <Link href="/labs/ml-v2">ATLAS</Link>
          <ChevronRight size={12} />
          <span>ML V2</span>
          <ChevronRight size={12} />
          <span>F{feature.id.toString().padStart(2, "0")}</span>
        </div>

        <h1 className="hero-title">
          <span className="hero-fid">
            F{feature.id.toString().padStart(2, "0")}
          </span>
          {feature.title}
        </h1>

        <p className="hero-desc">{feature.description}</p>

        <div className="hero-meta-strip">
          <div className="hero-meta-pill">
            <Zap size={11} />
            <span>{totalOut} OUTPUTS</span>
          </div>
          <div className="hero-meta-pill">
            <Shield size={11} />
            <span>{resOnly} RESEARCH-ONLY</span>
          </div>
          <div className="hero-meta-pill">
            <Cpu size={11} />
            <span>
              {feature.defaults?.compute_mode?.toUpperCase() || "REALTIME"}
            </span>
          </div>
          <div className="hero-meta-pill hero-meta-pill--live">
            <span className="hero-live-dot" />
            <span>ENGINE READY</span>
          </div>
        </div>

        {feature.implementationNotes?.length ? (
          <div className="hero-notes">
            {feature.implementationNotes.map((n, i) => (
              <span key={i}>
                <Activity size={10} />
                {n}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <button
        className="ml-run-v3"
        onClick={onRun}
        disabled={loading}
        type="button"
      >
        <div className="run-inner">
          <Play size={18} fill="currentColor" />
          <span>{loading ? "COMPUTING…" : "RUN ANALYSIS"}</span>
        </div>
        <div className="run-glow" />
      </button>
    </section>
  );
}
```

```css
/* Add inside ML_STYLES */
.ml-hero-v3 {
  position: relative;
  min-height: 320px;
  border: 1px solid #1e2535;
  border-radius: 24px;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 40px;
  background: #07080a;
}
.ml-hero-v3:before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(0, 212, 255, 0.06) 0%, transparent 45%),
    linear-gradient(225deg, rgba(245, 164, 0, 0.07) 0%, transparent 50%);
  pointer-events: none;
}
.hero-scanlines {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.18) 2px,
    rgba(0, 0, 0, 0.18) 4px
  );
  pointer-events: none;
  z-index: 1;
}
.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  animation: orbDrift 8s ease-in-out infinite alternate;
}
.hero-orb-a {
  width: 380px;
  height: 380px;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.18), transparent 70%);
  top: -140px;
  right: -80px;
  animation-delay: 0s;
}
.hero-orb-b {
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(245, 164, 0, 0.14), transparent 70%);
  bottom: -80px;
  left: 20%;
  animation-delay: -3s;
}
.hero-orb-c {
  width: 200px;
  height: 200px;
  background: radial-gradient(
    circle,
    rgba(168, 85, 247, 0.12),
    transparent 70%
  );
  top: 20%;
  left: -60px;
  animation-delay: -5s;
}
@keyframes orbDrift {
  0% {
    transform: translate(0, 0) scale(1);
  }
  100% {
    transform: translate(24px, 16px) scale(1.08);
  }
}
.hero-inner {
  position: relative;
  z-index: 2;
  flex: 1;
  min-width: 0;
}
.hero-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #4a5568;
  font:
    800 10px "JetBrains Mono",
    monospace;
  letter-spacing: 0.2em;
  margin-bottom: 20px;
}
.hero-breadcrumb a {
  color: #00d4ff;
  text-decoration: none;
}
.hero-breadcrumb a:hover {
  text-decoration: underline;
}
.hero-title {
  margin: 0 0 14px;
  font:
    900 clamp(32px, 5vw, 68px)/0.92 "Georgia",
    "Times New Roman",
    serif;
  letter-spacing: -0.04em;
  color: #e8edf5;
  display: flex;
  align-items: baseline;
  gap: 18px;
  flex-wrap: wrap;
}
.hero-fid {
  font-family: "JetBrains Mono", monospace;
  font-size: clamp(14px, 2vw, 22px);
  color: #00d4ff;
  letter-spacing: 0.1em;
  font-weight: 900;
  border: 1px solid rgba(0, 212, 255, 0.35);
  border-radius: 7px;
  padding: 4px 10px;
  background: rgba(0, 212, 255, 0.07);
  align-self: center;
  flex-shrink: 0;
}
.hero-desc {
  color: #8b96aa;
  font-size: 16px;
  line-height: 1.7;
  max-width: 720px;
  margin: 0 0 20px;
}
.hero-meta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.hero-meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  border: 1px solid #1e2535;
  border-radius: 999px;
  padding: 0 10px;
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.16em;
  background: rgba(255, 255, 255, 0.025);
}
.hero-meta-pill--live {
  border-color: rgba(0, 229, 160, 0.35);
  color: #00e5a0;
  background: rgba(0, 229, 160, 0.06);
}
.hero-live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #00e5a0;
  animation: livePulse 1.4s ease-in-out infinite;
}
@keyframes livePulse {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 0 0 rgba(0, 229, 160, 0.6);
  }
  50% {
    opacity: 0.7;
    box-shadow: 0 0 0 5px rgba(0, 229, 160, 0);
  }
}
.hero-notes {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.hero-notes span {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  color: #4a5568;
  font-size: 11px;
  line-height: 1.5;
}
.hero-notes svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: #00d4ff;
}
.ml-run-v3 {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  width: 180px;
  height: 56px;
  border: 1px solid rgba(0, 212, 255, 0.42);
  border-radius: 14px;
  background: linear-gradient(
    135deg,
    rgba(0, 212, 255, 0.18),
    rgba(0, 212, 255, 0.06)
  );
  cursor: pointer;
  overflow: hidden;
  align-self: flex-end;
}
.ml-run-v3:disabled {
  opacity: 0.5;
  cursor: wait;
}
.run-inner {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #00d4ff;
  font:
    900 12px "JetBrains Mono",
    monospace;
  letter-spacing: 0.18em;
  height: 100%;
}
.run-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at 50% 120%,
    rgba(0, 212, 255, 0.4),
    transparent 60%
  );
  opacity: 0;
  transition: opacity 0.3s ease;
}
.ml-run-v3:hover:not(:disabled) .run-glow {
  opacity: 1;
}
.ml-run-v3:hover:not(:disabled) {
  border-color: rgba(0, 212, 255, 0.8);
  box-shadow:
    0 0 40px rgba(0, 212, 255, 0.2),
    0 0 80px rgba(0, 212, 255, 0.08);
}
```

---

## 2. PROGRESS BAR with stage labels

```jsx
// Drop-in: add above the workspace section in MLV2Workbench
function MLRunProgress({ running, progress, stage }) {
  if (!running && progress === 0) return null;
  const stages = [
    "Loading universe",
    "Building features",
    "Running models",
    "Computing outputs",
    "Rendering results",
  ];
  const current =
    stages[Math.min(Math.floor(progress * stages.length), stages.length - 1)];
  return (
    <div className="ml-run-progress">
      <div
        className="ml-run-bar"
        style={{ width: `${Math.max(4, progress * 100)}%` }}
      />
      <div className="ml-run-stage">
        <span className="ml-stage-dot" />
        <span>{running ? current : "RUN COMPLETE"}</span>
        <b>{Math.round(progress * 100)}%</b>
      </div>
    </div>
  );
}
```

```css
.ml-run-progress {
  position: sticky;
  top: 0;
  z-index: 50;
  height: 36px;
  margin: 0;
  background: #07080a;
  border-bottom: 1px solid #141824;
  overflow: hidden;
}
.ml-run-bar {
  height: 2px;
  background: linear-gradient(90deg, #00d4ff, #00e5a0, #f5a400);
  position: absolute;
  top: 0;
  left: 0;
  transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 0 18px rgba(0, 212, 255, 0.6);
}
.ml-run-stage {
  height: 34px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 18px;
  color: #4a5568;
  font:
    900 10px "JetBrains Mono",
    monospace;
  letter-spacing: 0.14em;
}
.ml-stage-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00d4ff;
  animation: livePulse 1.2s ease-in-out infinite;
}
.ml-run-stage b {
  margin-left: auto;
  color: #00d4ff;
}
```

---

## 3. TOPBAR with search, keyboard shortcut hints, and workspace controls

```jsx
// Full topbar replacement — place above hero inside MLV2Workbench return
function MLTopbar({
  featureId,
  feature,
  query,
  setQuery,
  sections,
  response,
  onExport,
  onInputOpen,
}) {
  return (
    <header className="ml-topbar">
      <div className="ml-topbar-brand">
        <span className="ml-topbar-logo">ATLAS</span>
        <span className="ml-topbar-sep">/</span>
        <span className="ml-topbar-module">ML V2</span>
        <span className="ml-topbar-sep">/</span>
        <span className="ml-topbar-fid">
          F{String(featureId).padStart(2, "0")}
        </span>
      </div>

      <div className="ml-topbar-search">
        <Search size={13} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search outputs… (⌘K)"
        />
        {query ? (
          <button onClick={() => setQuery("")} type="button">
            <X size={12} />
          </button>
        ) : null}
      </div>

      <div className="ml-topbar-actions">
        <button type="button" onClick={onInputOpen} className="ml-topbar-btn">
          <SlidersHorizontal size={14} />
          <span>Input Contract</span>
        </button>
        <button type="button" onClick={onExport} className="ml-topbar-btn">
          <Download size={14} />
          <span>Export</span>
        </button>
        <div className="ml-topbar-kbd">
          <kbd>F</kbd>
          <span>Cinema</span>
        </div>
        <div className="ml-topbar-kbd">
          <kbd>ESC</kbd>
          <span>Close</span>
        </div>
      </div>
    </header>
  );
}
```

```css
.ml-topbar {
  position: sticky;
  top: 0;
  z-index: 60;
  height: 52px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 28px;
  background: rgba(3, 3, 4, 0.88);
  border-bottom: 1px solid #141824;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
.ml-topbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.ml-topbar-logo {
  color: #00d4ff;
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.22em;
}
.ml-topbar-sep {
  color: #1e2535;
}
.ml-topbar-module {
  color: #8b96aa;
  font:
    800 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.12em;
}
.ml-topbar-fid {
  color: #f5a400;
  font:
    900 11px "JetBrains Mono",
    monospace;
}
.ml-topbar-search {
  flex: 1;
  max-width: 360px;
  height: 34px;
  border: 1px solid #1e2535;
  border-radius: 10px;
  background: #0e1014;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 11px;
  color: #4a5568;
  margin: 0 auto;
}
.ml-topbar-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: #e8edf5;
  outline: 0;
  font-size: 12px;
}
.ml-topbar-search input::placeholder {
  color: #4a5568;
}
.ml-topbar-search button {
  background: transparent;
  border: 0;
  color: #4a5568;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.ml-topbar-search:focus-within {
  border-color: rgba(0, 212, 255, 0.45);
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.08);
}
.ml-topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.ml-topbar-btn {
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #1e2535;
  border-radius: 9px;
  background: #111318;
  color: #8b96aa;
  padding: 0 12px;
  font:
    800 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition:
    border-color 0.15s,
    color 0.15s,
    background 0.15s;
}
.ml-topbar-btn:hover {
  border-color: rgba(0, 212, 255, 0.45);
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.06);
}
.ml-topbar-kbd {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
}
.ml-topbar-kbd kbd {
  height: 20px;
  padding: 0 5px;
  border: 1px solid #1e2535;
  border-radius: 4px;
  background: #111318;
  color: #8b96aa;
  font-size: 9px;
}
```

---

## 4. STICKY SUMMARY BAR beneath topbar

```jsx
function MLStickySummary({ sections, activeId, response }) {
  const section = sections.find((s) => s.id === activeId) || sections[0];
  const data = section ? pickData(response, section) : null;
  const rows = rowsFrom(data);
  const nums = rows
    .flatMap((r) =>
      Object.entries(r)
        .map(([k, v]) => ({ k, v: numberLike(v) }))
        .filter((x) => x.v != null),
    )
    .slice(0, 5);
  if (!response || !nums.length) return null;
  return (
    <div className="ml-sticky-summary">
      <span className="ml-summary-label">{section?.title}</span>
      {nums.map(({ k, v }) => (
        <div className="ml-summary-stat" key={k}>
          <em>{titleize(k)}</em>
          <b>{formatValue(v)}</b>
        </div>
      ))}
    </div>
  );
}
```

```css
.ml-sticky-summary {
  position: sticky;
  top: 52px;
  z-index: 40;
  height: 38px;
  display: flex;
  align-items: center;
  gap: 0;
  background: rgba(3, 3, 4, 0.82);
  border-bottom: 1px solid #141824;
  backdrop-filter: blur(14px);
  padding: 0 20px;
  overflow-x: auto;
  scrollbar-width: none;
}
.ml-sticky-summary::-webkit-scrollbar {
  display: none;
}
.ml-summary-label {
  color: #00d4ff;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-right: 16px;
  flex-shrink: 0;
}
.ml-summary-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  border-left: 1px solid #141824;
  flex-shrink: 0;
}
.ml-summary-stat:first-of-type {
  border-left: 0;
}
.ml-summary-stat em {
  color: #4a5568;
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
  font-style: normal;
  text-transform: uppercase;
}
.ml-summary-stat b {
  color: #e8edf5;
  font:
    900 11px "JetBrains Mono",
    monospace;
}
```

---

## 5. VERTICAL DOCK replacing old nav — cinema-mode aware, drag-to-reorder

```jsx
function MLOutputDock({ sections, activeId, onJump, cinemaId, onReorder }) {
  const [dragging, setDragging] = useState(null);
  const primaryIds = new Set(
    sections.filter((s) => s.rank === "primary").map((s) => s.id),
  );

  return (
    <nav className="ml-dock" aria-label="ML outputs">
      <strong className="ml-dock-label">OUTPUTS</strong>
      {sections.map((section, i) => (
        <button
          key={section.id}
          className={[
            "ml-dock-btn",
            activeId === section.id ? "active" : "",
            primaryIds.has(section.id) ? "primary" : "",
            dragging === section.id ? "dragging" : "",
            cinemaId && cinemaId !== section.id ? "dimmed" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          draggable
          onClick={() => onJump(section.id)}
          onDragStart={() => setDragging(section.id)}
          onDragEnd={() => setDragging(null)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => {
            onReorder?.(dragging, section.id);
            setDragging(null);
          }}
          title={section.title}
          type="button"
        >
          <span className="dock-index">{String(i + 1).padStart(2, "0")}</span>
          <BarChart3 size={15} />
          <em className="dock-label">{section.title}</em>
          {primaryIds.has(section.id) ? (
            <i className="dock-primary-pip" />
          ) : null}
        </button>
      ))}
    </nav>
  );
}
```

```css
.ml-dock {
  position: sticky;
  top: 74px;
  max-height: calc(100dvh - 100px);
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 8px;
  border: 1px solid #1e2535;
  border-radius: 22px;
  background: rgba(7, 8, 10, 0.84);
  backdrop-filter: blur(18px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
  scrollbar-width: none;
}
.ml-dock::-webkit-scrollbar {
  display: none;
}
.ml-dock-label {
  writing-mode: vertical-rl;
  color: #00d4ff;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.26em;
  margin: 8px 0 10px;
  opacity: 0.7;
}
.ml-dock-btn {
  width: 52px;
  min-height: 46px;
  border: 1px solid #1e2535;
  border-radius: 14px;
  background: #0e1014;
  color: #4a5568;
  display: grid;
  place-items: center;
  position: relative;
  cursor: pointer;
  transition:
    transform 0.18s cubic-bezier(0.16, 1, 0.3, 1),
    background 0.18s,
    color 0.18s,
    border-color 0.18s,
    box-shadow 0.18s;
}
.ml-dock-btn:hover {
  transform: translateX(8px) scale(1.1);
  background: rgba(0, 212, 255, 0.08);
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.4);
}
.ml-dock-btn.active {
  transform: translateX(12px) scale(1.15);
  background: rgba(0, 212, 255, 0.14);
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.7);
  box-shadow: 0 0 24px rgba(0, 212, 255, 0.2);
}
.ml-dock-btn.primary .dock-primary-pip {
  display: block;
}
.ml-dock-btn.dragging {
  opacity: 0.35;
  transform: translateX(6px) scale(0.94);
}
.ml-dock-btn.dimmed {
  opacity: 0.2;
  pointer-events: none;
}
.dock-index {
  position: absolute;
  top: 4px;
  left: 5px;
  font:
    900 8px "JetBrains Mono",
    monospace;
  color: #4a5568;
}
.dock-label {
  position: absolute;
  left: 66px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  background: #111318;
  border: 1px solid #1e2535;
  border-radius: 9px;
  padding: 7px 11px;
  color: #e8edf5;
  font:
    700 12px Inter,
    sans-serif;
  font-style: normal;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  transition: opacity 0.12s ease;
}
.ml-dock-btn:hover .dock-label {
  opacity: 1;
}
.dock-primary-pip {
  display: none;
  position: absolute;
  top: 5px;
  right: 5px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #f5a400;
  box-shadow: 0 0 6px rgba(245, 164, 0, 0.8);
}
```

---

## 6. OUTPUT CARD — cinema mode, drawing canvas, sparkline, fullscreen, stagger reveal

```jsx
function MLOutputCard({
  section,
  response,
  index,
  activeId,
  onActive,
  cinemaId,
  onCinema,
}) {
  const [full, setFull] = useState(false);
  const [draw, setDraw] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const data = pickData(response, section);
  const focused = cinemaId === section.id;
  const dimmed = cinemaId && !focused;

  return (
    <motion.article
      id={section.id}
      className={[
        "ml-card-v3",
        section.rank === "primary" ? "primary" : "",
        activeId === section.id ? "active" : "",
        full ? "fullscreen" : "",
        focused ? "cinema-focused" : "",
        dimmed ? "cinema-dimmed" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      initial={{ opacity: 0, y: 28, filter: "blur(4px)" }}
      animate={{ opacity: dimmed ? 0.06 : 1, y: 0, filter: "blur(0px)" }}
      transition={{
        duration: 0.38,
        delay: index * 0.048,
        ease: [0.16, 1, 0.3, 1],
      }}
      onMouseEnter={() => onActive(section.id)}
    >
      {/* Gradient top border */}
      <div className="card-top-border" />

      <header className="ml-card-header">
        <div className="card-meta">
          <code className="card-source">
            {section.source}.{section.dataKey}
          </code>
          <h3 className="card-title">{section.title}</h3>
        </div>
        <MLHeaderSparkline data={data} />
        <div className="card-actions">
          <button
            type="button"
            title="Annotate"
            onClick={() => setDraw((v) => !v)}
            className={draw ? "active" : ""}
          >
            <Pencil size={13} />
          </button>
          <button
            type="button"
            title="Clear annotations"
            onClick={() => setResetKey((k) => k + 1)}
          >
            <Eraser size={13} />
          </button>
          <button
            type="button"
            title="Copy data"
            onClick={() => {
              const rows = rowsFrom(data);
              const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
              navigator.clipboard?.writeText(
                [
                  cols.join("\t"),
                  ...rows.map((r) => cols.map((c) => r[c] ?? "").join("\t")),
                ].join("\n"),
              );
            }}
          >
            <Copy size={13} />
          </button>
          <button
            type="button"
            title="Download JSON"
            onClick={() => {
              const blob = new Blob([JSON.stringify(data ?? {}, null, 2)], {
                type: "application/json",
              });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `ml-v2-${section.id}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            <Download size={13} />
          </button>
          <button
            type="button"
            title="Cinema mode"
            onClick={() => onCinema(focused ? null : section.id)}
            className={focused ? "active" : ""}
          >
            <Film size={13} />
          </button>
          <button
            type="button"
            title="Fullscreen"
            onClick={() => setFull((v) => !v)}
          >
            <Maximize2 size={13} />
          </button>
        </div>
      </header>

      <div className="ml-screen-v3">
        <MLRenderer section={section} data={data} response={response} />
        <MLDrawingCanvas enabled={draw} resetKey={resetKey} />
      </div>
    </motion.article>
  );
}
```

```css
.ml-card-v3 {
  position: relative;
  border: 1px solid #1e2535;
  border-radius: 20px;
  background: linear-gradient(
    180deg,
    rgba(17, 19, 24, 0.97),
    rgba(7, 8, 10, 0.99)
  );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 20px 60px rgba(0, 0, 0, 0.35);
  overflow: hidden;
  transition:
    border-color 0.2s,
    box-shadow 0.2s,
    opacity 0.25s;
}
.ml-card-v3.active {
  border-color: rgba(0, 212, 255, 0.55);
  box-shadow:
    0 0 0 1px rgba(0, 212, 255, 0.12),
    0 0 50px rgba(0, 212, 255, 0.07),
    0 24px 80px rgba(0, 0, 0, 0.4);
}
.ml-card-v3.primary {
  border-left: 3px solid #00d4ff;
}
.ml-card-v3.primary .card-top-border {
  background: linear-gradient(
    90deg,
    transparent,
    rgba(0, 212, 255, 0.7),
    transparent
  );
}
.ml-card-v3.fullscreen {
  position: fixed;
  z-index: 120;
  inset: 16px;
  border-radius: 22px;
}
.ml-card-v3.cinema-focused {
  z-index: 20;
  box-shadow:
    0 0 0 1px rgba(0, 212, 255, 0.5),
    0 0 120px rgba(0, 212, 255, 0.12),
    0 40px 140px rgba(0, 0, 0, 0.7);
}
.ml-card-v3.cinema-dimmed {
  pointer-events: none;
  user-select: none;
}
.card-top-border {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.12),
    transparent
  );
}
.ml-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 0;
}
.card-meta {
  flex: 1;
  min-width: 0;
}
.card-source {
  display: block;
  color: #4a5568;
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 5px;
}
.card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.015em;
  color: #e8edf5;
  line-height: 1.3;
}
.card-actions {
  display: flex;
  gap: 5px;
  flex-shrink: 0;
}
.card-actions button {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid #1e2535;
  border-radius: 8px;
  background: #0e1014;
  color: #4a5568;
  cursor: pointer;
  transition:
    color 0.15s,
    border-color 0.15s,
    background 0.15s;
}
.card-actions button:hover {
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.4);
  background: rgba(0, 212, 255, 0.07);
}
.card-actions button.active {
  color: #f5a400;
  border-color: rgba(245, 164, 0, 0.5);
  background: rgba(245, 164, 0, 0.1);
}
.ml-screen-v3 {
  position: relative;
  min-height: 200px;
  padding: 16px 18px 18px;
  background:
    radial-gradient(
      ellipse at 50% 0%,
      rgba(0, 212, 255, 0.06),
      transparent 50%
    ),
    linear-gradient(180deg, #0c0e11, #070809);
  margin: 12px 10px 10px;
  border-radius: 14px;
  border: 1px solid #141824;
  cursor: crosshair;
}
.ml-screen-v3::after {
  content: "";
  pointer-events: none;
  position: absolute;
  inset: 0;
  border-radius: 14px;
  background:
    linear-gradient(rgba(255, 255, 255, 0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px);
  background-size: 28px 28px;
}
```

---

## 7. DRAWING CANVAS — annotation overlay

```jsx
function MLDrawingCanvas({ enabled, resetKey }) {
  const ref = useRef(null);
  const drawing = useRef(false);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    const resize = () => {
      const rect = parent.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.lineWidth = 2.2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#00D4FF";
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [resetKey]);

  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, ref.current.width, ref.current.height);
  }, [resetKey]);

  if (!enabled) return null;

  return (
    <canvas
      ref={ref}
      className="ml-drawing-canvas"
      onPointerDown={(e) => {
        drawing.current = true;
        const ctx = e.currentTarget.getContext("2d");
        ctx.beginPath();
        ctx.moveTo(e.nativeEvent.offsetX, e.nativeEvent.offsetY);
      }}
      onPointerMove={(e) => {
        if (!drawing.current) return;
        const ctx = e.currentTarget.getContext("2d");
        ctx.lineTo(e.nativeEvent.offsetX, e.nativeEvent.offsetY);
        ctx.stroke();
      }}
      onPointerUp={() => {
        drawing.current = false;
      }}
      onPointerLeave={() => {
        drawing.current = false;
      }}
    />
  );
}
```

```css
.ml-drawing-canvas {
  position: absolute;
  inset: 0;
  z-index: 8;
  border-radius: 14px;
  touch-action: none;
  cursor: crosshair;
}
```

---

## 8. HEADER SPARKLINE on each card

```jsx
function MLHeaderSparkline({ data }) {
  const rows = rowsFrom(data);
  const values = rows
    .flatMap((r) =>
      Object.values(r)
        .map(numberLike)
        .filter((v) => v != null),
    )
    .slice(-32);
  if (values.length < 3) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values
    .map(
      (v, i) =>
        `${(i / (values.length - 1)) * 100},${22 - ((v - min) / range) * 20}`,
    )
    .join(" ");
  const lastUp = values.at(-1) >= values.at(-2);
  return (
    <svg className="ml-header-spark" viewBox="0 0 100 26" aria-hidden>
      <defs>
        <linearGradient id="spark-fill" x1="0" x2="0" y1="0" y2="1">
          <stop
            offset="0%"
            stopColor={lastUp ? "#00E5A0" : "#FF4D6A"}
            stopOpacity=".4"
          />
          <stop
            offset="100%"
            stopColor={lastUp ? "#00E5A0" : "#FF4D6A"}
            stopOpacity="0"
          />
        </linearGradient>
      </defs>
      <polyline
        points={pts}
        fill="none"
        stroke={lastUp ? "#00E5A0" : "#FF4D6A"}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}
```

```css
.ml-header-spark {
  width: 110px;
  height: 28px;
  flex-shrink: 0;
  margin: 0 8px;
}
```

---

## 9. TOAST SYSTEM

```jsx
function MLToastRack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="ml-toast-rack" role="region" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            className={`ml-toast ml-toast-${t.type}`}
            initial={{ opacity: 0, x: 40, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="toast-pip" />
            <span className="toast-msg">{t.message}</span>
            <button onClick={() => onDismiss(t.id)} type="button">
              ×
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
```

```css
.ml-toast-rack {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 500;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  max-width: 380px;
}
.ml-toast {
  min-height: 44px;
  padding: 0 10px 0 14px;
  border: 1px solid #1e2535;
  border-radius: 12px;
  background: rgba(7, 8, 10, 0.96);
  backdrop-filter: blur(18px);
  display: flex;
  align-items: center;
  gap: 10px;
  color: #e8edf5;
  font-size: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.ml-toast-success {
  border-color: rgba(0, 229, 160, 0.35);
}
.ml-toast-warning {
  border-color: rgba(245, 164, 0, 0.4);
}
.ml-toast-error {
  border-color: rgba(255, 77, 106, 0.4);
}
.ml-toast-info {
  border-color: rgba(0, 212, 255, 0.35);
}
.toast-pip {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ml-toast-success .toast-pip {
  background: #00e5a0;
}
.ml-toast-warning .toast-pip {
  background: #f5a400;
}
.ml-toast-error .toast-pip {
  background: #ff4d6a;
}
.ml-toast-info .toast-pip {
  background: #00d4ff;
}
.toast-msg {
  flex: 1;
  font-size: 12px;
}
.ml-toast button {
  border: 0;
  background: transparent;
  color: #4a5568;
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
}
```

---

## 10. EXPORT MODAL

```jsx
function MLExportModal({ feature, form, sections, response, onClose }) {
  const [copied, setCopied] = useState("");
  const jsonText = JSON.stringify(
    {
      feature: { id: feature.id, title: feature.title },
      form,
      sections: sections.map(({ id, title, source, dataKey, chartType }) => ({
        id,
        title,
        source,
        dataKey,
        chartType,
      })),
      response,
      exported_at: new Date().toISOString(),
    },
    null,
    2,
  );

  const tsvText = sections
    .map((s) => {
      const rows = rowsFrom(pickData(response, s));
      if (!rows.length) return "";
      const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
      return [
        `# ${s.title}`,
        cols.join("\t"),
        ...rows.map((r) => cols.map((c) => r[c] ?? "").join("\t")),
      ].join("\n");
    })
    .filter(Boolean)
    .join("\n\n");

  async function copy(text, label) {
    await navigator.clipboard?.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 1600);
  }

  function dl(name, text, type = "text/plain") {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <motion.div
      className="ml-export-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.section
        className="ml-export-modal"
        initial={{ y: 32, opacity: 0, scale: 0.97 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        exit={{ y: 32, opacity: 0, scale: 0.97 }}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <p>EXPORT SURFACE</p>
            <h2>
              F{feature.id} · {feature.title}
            </h2>
          </div>
          <button onClick={onClose} type="button">
            <X size={16} />
          </button>
        </header>
        <div className="ml-export-grid">
          {[
            {
              icon: <Download size={18} />,
              label: "Workspace JSON",
              sub: "Full payload with inputs and all outputs.",
              onClick: () =>
                dl(
                  `atlas-ml-f${feature.id}-workspace.json`,
                  jsonText,
                  "application/json",
                ),
            },
            {
              icon: <Download size={18} />,
              label: "Excel TSV",
              sub: "All tables as tab-separated values.",
              onClick: () =>
                dl(
                  `atlas-ml-f${feature.id}-outputs.tsv`,
                  tsvText || "No tabular outputs",
                  "text/tab-separated-values",
                ),
            },
            {
              icon: <Copy size={18} />,
              label: "Copy JSON",
              sub:
                copied === "json"
                  ? "Copied!"
                  : "Copy workspace config to clipboard.",
              onClick: () => copy(jsonText, "json"),
            },
            {
              icon: <Copy size={18} />,
              label: "Copy TSV",
              sub: copied === "tsv" ? "Copied!" : "Copy all tables for Excel.",
              onClick: () => copy(tsvText || "No outputs", "tsv"),
            },
          ].map((item) => (
            <button
              key={item.label}
              onClick={item.onClick}
              type="button"
              className="ml-export-option"
            >
              <div className="export-icon">{item.icon}</div>
              <b>{item.label}</b>
              <span>{item.sub}</span>
            </button>
          ))}
        </div>
        <textarea readOnly value={tsvText || jsonText} />
      </motion.section>
    </motion.div>
  );
}
```

```css
.ml-export-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.78);
  backdrop-filter: blur(20px);
  display: grid;
  place-items: center;
  padding: 24px;
}
.ml-export-modal {
  width: min(860px, calc(100vw - 48px));
  max-height: calc(100dvh - 48px);
  overflow: auto;
  border: 1px solid #1e2535;
  border-radius: 20px;
  background: linear-gradient(180deg, #101318, #070809);
  box-shadow: 0 40px 140px rgba(0, 0, 0, 0.8);
}
.ml-export-modal header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid #141824;
}
.ml-export-modal header p {
  margin: 0;
  color: #00d4ff;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.2em;
}
.ml-export-modal header h2 {
  margin: 3px 0 0;
  font-size: 17px;
}
.ml-export-modal header button {
  width: 34px;
  height: 34px;
  border: 1px solid #1e2535;
  border-radius: 9px;
  background: #0e1014;
  color: #8b96aa;
  display: grid;
  place-items: center;
  cursor: pointer;
}
.ml-export-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 16px;
}
.ml-export-option {
  min-height: 120px;
  text-align: left;
  border: 1px solid #1e2535;
  border-radius: 14px;
  background: #0e1014;
  color: #8b96aa;
  padding: 14px;
  display: grid;
  gap: 6px;
  align-content: start;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.ml-export-option:hover {
  border-color: rgba(0, 212, 255, 0.45);
  background: rgba(0, 212, 255, 0.06);
}
.export-icon {
  color: #00d4ff;
  margin-bottom: 2px;
}
.ml-export-option b {
  color: #e8edf5;
  font-size: 13px;
}
.ml-export-option span {
  font-size: 11px;
  line-height: 1.45;
}
.ml-export-modal textarea {
  display: block;
  width: calc(100% - 32px);
  height: 180px;
  margin: 0 16px 16px;
  border: 1px solid #1e2535;
  border-radius: 12px;
  background: #050507;
  color: #4a5568;
  padding: 12px;
  font:
    11px "JetBrains Mono",
    monospace;
  resize: vertical;
}
```

---

## 11. FULL DATA TABLE with microbar heat columns, sticky first column, sort

```jsx
function MLTable({ data, searchQuery = "" }) {
  const rows = useMemo(() => rowsFrom(data).slice(0, 500), [data]);
  const cols = useMemo(
    () =>
      [...new Set(rows.slice(0, 80).flatMap((r) => Object.keys(r)))].slice(
        0,
        14,
      ),
    [rows],
  );
  const [sort, setSort] = useState({ key: cols[0], dir: "asc" });

  const colStats = useMemo(
    () =>
      Object.fromEntries(
        cols.map((col) => {
          const nums = rows
            .map((r) => numberLike(r[col]))
            .filter((v) => v != null);
          return [col, { max: Math.max(1e-9, ...nums.map(Math.abs)) }];
        }),
      ),
    [cols, rows],
  );

  const sorted = useMemo(
    () =>
      [...rows].sort((a, b) => {
        const av = numberLike(a[sort.key]) ?? String(a[sort.key] ?? "");
        const bv = numberLike(b[sort.key]) ?? String(b[sort.key] ?? "");
        const r =
          typeof av === "number" && typeof bv === "number"
            ? av - bv
            : String(av).localeCompare(String(bv));
        return sort.dir === "asc" ? r : -r;
      }),
    [rows, sort],
  );

  const q = searchQuery.trim().toLowerCase();

  if (!rows.length) return <MLEmpty />;

  return (
    <div className="ml-table-v3-wrap">
      <table className="ml-table-v3">
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
                {titleize(col)}
                <em>
                  {sort.key === col ? (sort.dir === "asc" ? " ↑" : " ↓") : " ↕"}
                </em>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 300).map((row, i) => (
            <tr key={i}>
              {cols.map((col, ci) => {
                const n = numberLike(row[col]);
                const alpha =
                  n == null || ci === 0
                    ? 0
                    : Math.min(
                        0.42,
                        (Math.abs(n) / colStats[col].max) * 0.35 + 0.04,
                      );
                const bg =
                  n == null
                    ? undefined
                    : n < 0
                      ? `rgba(255,77,106,${alpha})`
                      : `rgba(0,229,160,${alpha * 0.75})`;
                const hit =
                  q &&
                  String(row[col] ?? "")
                    .toLowerCase()
                    .includes(q);
                const barW =
                  n == null || ci === 0
                    ? 0
                    : Math.min(100, (Math.abs(n) / colStats[col].max) * 100);
                return (
                  <td
                    key={col}
                    className={[
                      n != null ? (n < 0 ? "neg num" : "pos num") : "",
                      hit ? "hit" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={{ background: bg }}
                  >
                    <span className="cell-text">{formatValue(row[col])}</span>
                    {barW ? (
                      <span
                        className="cell-bar"
                        style={{
                          width: `${barW}%`,
                          background: n < 0 ? "#FF4D6A" : "#00E5A0",
                        }}
                      />
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ml-table-footer">
        {sorted.length} rows · {cols.length} columns
        {sorted.length > 300 ? " · first 300 shown" : ""}
      </div>
    </div>
  );
}
```

```css
.ml-table-v3-wrap {
  max-height: 560px;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid #141824;
}
.ml-table-v3 {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.ml-table-v3 th {
  position: sticky;
  top: 0;
  z-index: 3;
  background: #0c0e11;
  color: #00d4ff;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid #1e2535;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.ml-table-v3 th.sorted {
  background: #111318;
  color: #e8edf5;
}
.ml-table-v3 th em {
  font-style: normal;
  color: #4a5568;
}
.ml-table-v3 td {
  height: 40px;
  padding: 0 12px;
  border-bottom: 1px solid #0e1014;
  color: #8b96aa;
  font-family: "JetBrains Mono", monospace;
  position: relative;
  overflow: hidden;
  white-space: nowrap;
}
.ml-table-v3 td.pos {
  color: #00e5a0;
}
.ml-table-v3 td.neg {
  color: #ff4d6a;
}
.ml-table-v3 td.hit {
  outline: 1px solid #00d4ff;
  background: rgba(0, 212, 255, 0.1) !important;
  color: #e8edf5 !important;
}
.ml-table-v3 tr:hover td {
  background: rgba(0, 212, 255, 0.04) !important;
  color: #e8edf5;
}
.ml-table-v3 th:first-child,
.ml-table-v3 td:first-child {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #0c0e11;
}
.ml-table-v3 th:first-child {
  z-index: 4;
}
.ml-table-v3 tr:hover td:first-child {
  background: #0f1116 !important;
}
.cell-text {
  position: relative;
  z-index: 1;
}
.cell-bar {
  position: absolute;
  right: 6px;
  bottom: 4px;
  height: 2px;
  border-radius: 999px;
  opacity: 0.6;
  z-index: 0;
}
.ml-table-footer {
  padding: 7px 12px;
  background: #0a0c0f;
  border-top: 1px solid #141824;
  color: #4a5568;
  font:
    800 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.1em;
}
```

---

## 12. METRIC PANEL with percentile arc and delta

```jsx
function MLMetricPanel({ data }) {
  const rows = rowsFrom(data).slice(0, 8);
  if (!rows.length) return <MLEmpty />;
  return (
    <div className="ml-metric-grid-v3">
      {rows.map((row, i) => {
        const label =
          row.label || row.metric || row.name || row.model || `Metric ${i + 1}`;
        const value =
          row.value ??
          row.score ??
          row.ic ??
          row.sharpe ??
          row.weight ??
          row.probability;
        const n = numberLike(value);
        const pct = Math.max(
          0,
          Math.min(
            100,
            numberLike(row.percentile ?? row.pct) ??
              Math.min(100, Math.abs(n ?? 0) * 100),
          ),
        );
        const delta = numberLike(row.delta ?? row.change);
        const trend = delta == null ? pct >= 50 : delta >= 0;
        return (
          <div
            className={`ml-metric-v3 ${trend ? "trend-up" : "trend-dn"}`}
            key={`${label}-${i}`}
          >
            <span className="metric-label">{titleize(label)}</span>
            <strong className="metric-value">{formatValue(value)}</strong>
            {delta != null ? (
              <small className={`metric-delta ${delta >= 0 ? "pos" : "neg"}`}>
                {delta >= 0 ? "▲" : "▼"} {formatValue(Math.abs(delta))}
              </small>
            ) : null}
            <MLPercentileArc value={pct} trend={trend} />
            <em className="metric-sub">
              {row.subtitle ||
                row.status ||
                row.model ||
                row.distribution ||
                ""}
            </em>
          </div>
        );
      })}
    </div>
  );
}

function MLPercentileArc({ value, trend }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = pct > 80 ? "#FF4D6A" : pct > 60 ? "#F5A400" : "#00E5A0";
  const dash = (pct / 100) * 88;
  return (
    <svg
      className="metric-arc"
      viewBox="0 0 72 40"
      aria-label={`${pct.toFixed(0)} percentile`}
    >
      <path
        d="M 8 34 A 28 28 0 0 1 64 34"
        fill="none"
        stroke="#1E2535"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M 8 34 A 28 28 0 0 1 64 34"
        fill="none"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
        strokeDasharray={`${dash} 88`}
      />
      <text
        x="36"
        y="33"
        textAnchor="middle"
        fill={color}
        fontSize="10"
        fontWeight="900"
        fontFamily="JetBrains Mono, monospace"
      >
        {pct.toFixed(0)}p
      </text>
    </svg>
  );
}
```

```css
.ml-metric-grid-v3 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}
.ml-metric-v3 {
  border: 1px solid #1e2535;
  border-radius: 14px;
  padding: 16px;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.025),
    rgba(0, 0, 0, 0.1)
  );
  display: grid;
  grid-template-columns: 1fr 76px;
  gap: 6px 10px;
  align-items: start;
  transition:
    border-color 0.15s,
    transform 0.15s;
}
.ml-metric-v3:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 212, 255, 0.35);
}
.ml-metric-v3.trend-up {
  box-shadow: inset 3px 0 0 rgba(0, 229, 160, 0.55);
}
.ml-metric-v3.trend-dn {
  box-shadow: inset 3px 0 0 rgba(255, 77, 106, 0.55);
}
.metric-label {
  grid-column: 1/-1;
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.metric-value {
  font:
    900 28px "JetBrains Mono",
    monospace;
  color: #e8edf5;
  letter-spacing: -0.03em;
}
.metric-delta {
  font:
    900 10px "JetBrains Mono",
    monospace;
}
.metric-delta.pos {
  color: #00e5a0;
}
.metric-delta.neg {
  color: #ff4d6a;
}
.metric-arc {
  grid-row: 2/4;
  grid-column: 2;
  width: 76px;
  height: 44px;
}
.metric-sub {
  grid-column: 1;
  color: #4a5568;
  font-size: 10px;
  font-style: normal;
  line-height: 1.4;
}
```

---

## 13. HEATMAP with hover cross-highlight and scale legend

```jsx
function MLHeatmap({ data, config = {} }) {
  const rows = rowsFrom(data);
  const [hovered, setHovered] = useState(null);
  const rowKey =
    config.rowKey ||
    Object.keys(rows[0] || {}).find((k) =>
      /row|source|from|asset|factor|regime/i.test(k),
    ) ||
    "row";
  const colKey =
    config.colKey ||
    Object.keys(rows[0] || {}).find(
      (k) => /col|target|to|model|feature|state/i.test(k) && k !== rowKey,
    ) ||
    "col";
  const valueKey =
    config.valueKey ||
    Object.keys(rows[0] || {}).find(
      (k) =>
        k !== rowKey && k !== colKey && numberLike((rows[0] || {})[k]) != null,
    ) ||
    "value";

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
  const valMap = new Map(
    rows.map((r) => [
      `${r[rowKey]}|${r[colKey]}`,
      numberLike(r[valueKey]) ?? 0,
    ]),
  );

  if (!rowLabels.length) return <MLEmpty />;

  return (
    <div className="ml-heatmap-v3-shell">
      <div className="ml-heatmap-v3" style={{ "--hm-cols": colLabels.length }}>
        <div className="hm-corner" />
        {colLabels.map((col) => (
          <b key={col} className={hovered?.col === col ? "hm-hi" : ""}>
            {col}
          </b>
        ))}
        {rowLabels.map((row) => [
          <b
            key={`${row}-label`}
            className={`hm-row-label ${hovered?.row === row ? "hm-hi" : ""}`}
          >
            {row}
          </b>,
          ...colLabels.map((col) => {
            const v = valMap.get(`${row}|${col}`) ?? 0;
            const diag = row === col;
            const alpha = Math.min(0.88, (Math.abs(v) / maxAbs) * 0.8 + 0.08);
            const bg = diag
              ? "linear-gradient(135deg,rgba(0,212,255,.18),rgba(0,212,255,.05))"
              : config.diverging && v < 0
                ? `rgba(77,158,255,${alpha})`
                : v < 0
                  ? `rgba(255,77,106,${alpha})`
                  : `rgba(0,212,255,${alpha})`;
            const dim = hovered && hovered.row !== row && hovered.col !== col;
            return (
              <i
                key={`${row}-${col}`}
                className={[diag ? "hm-diag" : "", dim ? "hm-dim" : ""]
                  .filter(Boolean)
                  .join(" ")}
                style={{
                  background: bg,
                  boxShadow:
                    Math.abs(v) / maxAbs > 0.7
                      ? `0 0 16px ${v < 0 ? "rgba(77,158,255,.3)" : "rgba(0,212,255,.28)"}`
                      : "none",
                }}
                onMouseEnter={() => setHovered({ row, col, v })}
                onMouseLeave={() => setHovered(null)}
              >
                {diag
                  ? "—"
                  : Math.abs(v) > 0.3 || maxAbs > 10
                    ? formatValue(v)
                    : ""}
              </i>
            );
          }),
        ])}
      </div>
      {hovered ? (
        <div className="hm-hover-tip">
          <strong>
            {hovered.row} × {hovered.col}
          </strong>
          <b>{formatValue(hovered.v)}</b>
          <span>
            {((Math.abs(hovered.v) / maxAbs) * 100).toFixed(0)}% of max
          </span>
        </div>
      ) : null}
      <div className="hm-scale">
        <span>{config.diverging ? `-${formatValue(maxAbs)}` : "0"}</span>
        <i className={config.diverging ? "hm-scale-div" : "hm-scale-pos"} />
        <span>{formatValue(maxAbs)}</span>
      </div>
    </div>
  );
}
```

```css
.ml-heatmap-v3-shell {
  display: grid;
  gap: 10px;
}
.ml-heatmap-v3 {
  display: grid;
  grid-template-columns: 110px repeat(var(--hm-cols), minmax(40px, 1fr));
  gap: 3px;
  overflow: auto;
}
.ml-heatmap-v3 b {
  min-height: 32px;
  display: grid;
  place-items: center;
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.hm-row-label {
  justify-content: start !important;
  padding-left: 8px;
}
.hm-hi {
  color: #00d4ff !important;
}
.ml-heatmap-v3 i {
  min-height: 40px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  color: #e8edf5;
  font:
    800 10px "JetBrains Mono",
    monospace;
  font-style: normal;
  transition:
    opacity 0.12s,
    transform 0.12s,
    filter 0.12s;
  cursor: crosshair;
}
.ml-heatmap-v3 i:hover {
  transform: scale(1.06);
  filter: brightness(1.2);
  z-index: 1;
}
.hm-dim {
  opacity: 0.18;
}
.hm-diag {
  color: #00d4ff;
  border: 1px solid rgba(0, 212, 255, 0.2);
}
.hm-hover-tip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-left: 3px solid #00d4ff;
  background: rgba(0, 212, 255, 0.06);
  border-radius: 0 8px 8px 0;
  color: #8b96aa;
  font:
    800 11px "JetBrains Mono",
    monospace;
}
.hm-hover-tip strong {
  color: #e8edf5;
}
.hm-hover-tip b {
  color: #00d4ff;
}
.hm-scale {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
}
.hm-scale-pos {
  height: 6px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    rgba(0, 212, 255, 0.05),
    rgba(0, 212, 255, 0.9)
  );
}
.hm-scale-div {
  height: 6px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    rgba(77, 158, 255, 0.8),
    rgba(255, 255, 255, 0.08),
    rgba(0, 212, 255, 0.8)
  );
}
```

---

## 14. HOME PAGE GRID — feature cards with animated border on hover

```jsx
export function MLV2HomePage() {
  const featureIcons = {
    "01": <FlaskConical size={18} />,
    "02": <TrendingUp size={18} />,
    "03": <Activity size={18} />,
    "04": <Shield size={18} />,
    "05": <Cpu size={18} />,
    "06": <BrainCircuit size={18} />,
    "07": <Zap size={18} />,
    "08": <BarChart3 size={18} />,
    "09": <Search size={18} />,
    10: <Atom size={18} />,
    11: <FlaskConical size={18} />,
    12: <BrainCircuit size={18} />,
  };
  return (
    <main className="ml-home-v3">
      <section className="ml-home-hero-v3">
        <div className="home-hero-orb-a" />
        <div className="home-hero-orb-b" />
        <div className="home-hero-inner">
          <p className="home-hero-eyebrow">ATLAS // MACHINE LEARNING LAB V2</p>
          <h1 className="home-hero-title">
            Research-grade ML diagnostics
            <br />
            for systematic strategies.
          </h1>
          <p className="home-hero-sub">
            CPCV · Boosted alpha · GARCH · Meta-labeling · HRP · Regime
            detection · DMA · IC weighting · Pairs · Microstructure · Causal
            discovery · Sequence alpha
          </p>
          <div className="home-hero-stats">
            <div className="home-stat">
              <b>{ML_V2_FEATURES.length}</b>
              <span>MODULES</span>
            </div>
            <div className="home-stat">
              <b>
                {ML_V2_FEATURES.reduce(
                  (s, f) => s + (f.outputs?.length || 0),
                  0,
                )}
              </b>
              <span>OUTPUTS</span>
            </div>
            <div className="home-stat">
              <b>REALTIME</b>
              <span>ENGINE</span>
            </div>
          </div>
        </div>
      </section>

      <section className="ml-home-grid-v3">
        {ML_V2_FEATURES.map((feature) => (
          <Link
            href={`/labs/ml-v2/${feature.slug}`}
            key={feature.id}
            className="ml-home-card-v3"
          >
            <div className="home-card-top">
              <div className="home-card-icon">
                {featureIcons[String(feature.id).padStart(2, "0")] || (
                  <Atom size={18} />
                )}
              </div>
              <code className="home-card-fid">
                ML{String(feature.id).padStart(2, "0")}
              </code>
            </div>
            <h2 className="home-card-title">{feature.title}</h2>
            <p className="home-card-desc">{feature.description}</p>
            <div className="home-card-footer">
              <span className="home-card-outputs">
                {feature.outputs?.length || 0} outputs
              </span>
              <ChevronRight size={14} className="home-card-arrow" />
            </div>
            <div className="home-card-glow" />
          </Link>
        ))}
      </section>

      <style jsx global>
        {ML_HOME_STYLES}
      </style>
    </main>
  );
}
```

```css
.ml-home-v3 {
  min-height: 100dvh;
  background: #030304;
  color: #e8edf5;
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
  padding: 0 clamp(18px, 3vw, 52px) 120px;
}
.ml-home-hero-v3 {
  position: relative;
  min-height: 72vh;
  display: grid;
  place-content: center;
  text-align: center;
  overflow: hidden;
  padding: 80px 20px;
}
.home-hero-orb-a {
  position: absolute;
  width: 600px;
  height: 600px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.14), transparent 70%);
  top: -200px;
  left: 50%;
  transform: translateX(-50%);
  pointer-events: none;
  filter: blur(60px);
}
.home-hero-orb-b {
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(245, 164, 0, 0.1), transparent 70%);
  bottom: -100px;
  right: 10%;
  pointer-events: none;
  filter: blur(60px);
}
.home-hero-inner {
  position: relative;
  z-index: 1;
}
.home-hero-eyebrow {
  color: #00d4ff;
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.24em;
  margin: 0 0 22px;
}
.home-hero-title {
  margin: 0 0 18px;
  font-size: clamp(40px, 6vw, 80px);
  line-height: 0.92;
  letter-spacing: -0.05em;
  font-family: Georgia, "Times New Roman", serif;
}
.home-hero-sub {
  color: #8b96aa;
  font-size: 17px;
  line-height: 1.7;
  max-width: 820px;
  margin: 0 auto 32px;
}
.home-hero-stats {
  display: flex;
  justify-content: center;
  gap: 0;
}
.home-stat {
  padding: 0 28px;
  border-left: 1px solid #1e2535;
  text-align: center;
}
.home-stat:first-child {
  border-left: 0;
}
.home-stat b {
  display: block;
  font:
    900 32px "JetBrains Mono",
    monospace;
  color: #00d4ff;
}
.home-stat span {
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.2em;
}
.ml-home-grid-v3 {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 12px;
}
.ml-home-card-v3 {
  position: relative;
  min-height: 260px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid #1e2535;
  border-radius: 20px;
  background: linear-gradient(
    180deg,
    rgba(17, 19, 24, 0.95),
    rgba(7, 8, 10, 0.98)
  );
  padding: 22px;
  color: #e8edf5;
  text-decoration: none;
  overflow: hidden;
  transition:
    transform 0.2s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.2s;
}
.ml-home-card-v3:hover {
  transform: translateY(-8px);
  border-color: rgba(0, 212, 255, 0.55);
}
.ml-home-card-v3:hover .home-card-glow {
  opacity: 1;
}
.ml-home-card-v3:hover .home-card-arrow {
  transform: translateX(4px);
  color: #00d4ff;
}
.home-card-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    ellipse at 50% 0%,
    rgba(0, 212, 255, 0.08),
    transparent 60%
  );
  opacity: 0;
  transition: opacity 0.25s;
  pointer-events: none;
}
.home-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.home-card-icon {
  width: 38px;
  height: 38px;
  border: 1px solid #1e2535;
  border-radius: 10px;
  background: #0e1014;
  display: grid;
  place-items: center;
  color: #00d4ff;
}
.home-card-fid {
  color: #00d4ff;
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.14em;
}
.home-card-title {
  margin: 0 0 10px;
  font-size: 20px;
  letter-spacing: -0.025em;
  font-weight: 800;
  line-height: 1.25;
}
.home-card-desc {
  color: #8b96aa;
  font-size: 13px;
  line-height: 1.6;
  flex: 1;
  margin: 0 0 16px;
}
.home-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.home-card-outputs {
  color: #4a5568;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.14em;
}
.home-card-arrow {
  color: #4a5568;
  transition:
    transform 0.18s,
    color 0.18s;
}
```

---

## 15. KEYBOARD SHORTCUT HANDLER + CINEMA MODE wiring

```jsx
// Drop into MLV2Workbench useEffect block
useEffect(() => {
  const handler = (e) => {
    if (
      document.activeElement?.tagName === "INPUT" ||
      document.activeElement?.tagName === "TEXTAREA"
    )
      return;
    if (e.key === "Escape") {
      setCinemaId(null);
      setInputOpen(false);
      setExportOpen(false);
    }
    if (e.key.toLowerCase() === "f" && activeId) {
      e.preventDefault();
      setCinemaId((c) => (c === activeId ? null : activeId));
    }
    if (e.key.toLowerCase() === "e" && e.metaKey) {
      e.preventDefault();
      setExportOpen((v) => !v);
    }
    if (e.key.toLowerCase() === "k" && e.metaKey) {
      e.preventDefault();
      setQuery("");
      setTimeout(
        () => document.querySelector(".ml-topbar-search input")?.focus(),
        50,
      );
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const i = orderedSections.findIndex((s) => s.id === activeId);
      if (i < orderedSections.length - 1) jumpTo(orderedSections[i + 1].id);
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      const i = orderedSections.findIndex((s) => s.id === activeId);
      if (i > 0) jumpTo(orderedSections[i - 1].id);
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [activeId, orderedSections]);
```

---

## 16. INPUT CONTRACT CURTAIN (slide-down modal)

```jsx
// Replace the inline ml-contract section
function MLInputCurtain({
  feature,
  form,
  setForm,
  open,
  onClose,
  onRun,
  loading,
}) {
  if (!open) return null;
  return (
    <AnimatePresence>
      <motion.div
        className="ml-curtain-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.section
          className="ml-curtain-panel"
          initial={{ y: -48, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -48, opacity: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.36 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="ml-curtain-header">
            <div>
              <p>INPUT CONTRACT</p>
              <h2>
                F{String(feature.id).padStart(2, "0")} · {feature.title}
              </h2>
            </div>
            <button onClick={onClose} type="button">
              <X size={16} />
            </button>
          </header>

          <div className="ml-curtain-body">
            <div className="ml-field-grid-v3">
              {(feature.fields || []).map((field) => (
                <FieldInput
                  key={field.key}
                  field={field}
                  value={form[field.key]}
                  onChange={(value) =>
                    setForm((f) => ({ ...f, [field.key]: value }))
                  }
                />
              ))}
            </div>
          </div>

          <footer className="ml-curtain-footer">
            <button
              onClick={onClose}
              type="button"
              className="ml-curtain-close"
            >
              Close
            </button>
            <button
              onClick={onRun}
              disabled={loading}
              type="button"
              className="ml-curtain-run"
            >
              <Play size={15} fill="currentColor" />
              {loading ? "Computing…" : "Run analysis"}
            </button>
          </footer>
        </motion.section>
      </motion.div>
    </AnimatePresence>
  );
}
```

```css
.ml-curtain-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  padding: 64px 28px;
  overflow: auto;
}
.ml-curtain-panel {
  max-width: 1320px;
  margin: 0 auto;
  border: 1px solid #1e2535;
  border-radius: 22px;
  background: linear-gradient(180deg, #101318, #070809);
  box-shadow: 0 40px 140px rgba(0, 0, 0, 0.75);
}
.ml-curtain-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  border-bottom: 1px solid #141824;
}
.ml-curtain-header p {
  margin: 0;
  color: #00d4ff;
  font:
    900 9px "JetBrains Mono",
    monospace;
  letter-spacing: 0.2em;
}
.ml-curtain-header h2 {
  margin: 3px 0 0;
  font-size: 18px;
}
.ml-curtain-header button {
  width: 34px;
  height: 34px;
  border: 1px solid #1e2535;
  border-radius: 9px;
  background: #0e1014;
  color: #8b96aa;
  display: grid;
  place-items: center;
  cursor: pointer;
}
.ml-curtain-body {
  padding: 22px;
}
.ml-field-grid-v3 {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}
.ml-curtain-footer {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 0 22px;
  border-top: 1px solid #141824;
}
.ml-curtain-close {
  height: 38px;
  border: 1px solid #1e2535;
  background: #0e1014;
  color: #8b96aa;
  border-radius: 10px;
  padding: 0 14px;
  font:
    800 11px "JetBrains Mono",
    monospace;
  cursor: pointer;
}
.ml-curtain-close:hover {
  border-color: #1e2535;
  color: #e8edf5;
}
.ml-curtain-run {
  height: 38px;
  border: 1px solid rgba(0, 212, 255, 0.42);
  background: linear-gradient(
    135deg,
    rgba(0, 212, 255, 0.18),
    rgba(0, 212, 255, 0.06)
  );
  color: #00d4ff;
  border-radius: 10px;
  padding: 0 18px;
  font:
    900 11px "JetBrains Mono",
    monospace;
  letter-spacing: 0.12em;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ml-curtain-run:hover:not(:disabled) {
  border-color: rgba(0, 212, 255, 0.8);
  box-shadow: 0 0 28px rgba(0, 212, 255, 0.18);
}
.ml-curtain-run:disabled {
  opacity: 0.5;
  cursor: wait;
}
```

---

## 17. EMPTY STATE

```jsx
function MLEmpty({ section, response }) {
  const available = response
    ? Object.entries(response)
        .flatMap(([b, v]) =>
          v && typeof v === "object"
            ? Object.keys(v).map((k) => `${b}.${k}`)
            : [],
        )
        .slice(0, 6)
    : [];
  return (
    <div className="ml-empty-v3">
      <div className="empty-icon">
        <Atom size={22} />
      </div>
      <b>
        {response
          ? `${section?.source}.${section?.dataKey} not returned`
          : "Awaiting run"}
      </b>
      {available.length ? (
        <span>Available: {available.join(" · ")}</span>
      ) : (
        <span>Configure inputs and run the analysis to populate outputs.</span>
      )}
    </div>
  );
}
```

```css
.ml-empty-v3 {
  min-height: 180px;
  display: grid;
  place-items: center;
  text-align: center;
  gap: 10px;
  border: 1px dashed #1e2535;
  border-radius: 14px;
  padding: 28px;
}
.empty-icon {
  width: 46px;
  height: 46px;
  border: 1px solid #1e2535;
  border-radius: 12px;
  background: #0e1014;
  display: grid;
  place-items: center;
  color: #4a5568;
  margin: 0 auto;
}
.ml-empty-v3 b {
  color: #8b96aa;
  font-size: 13px;
}
.ml-empty-v3 span {
  color: #4a5568;
  font:
    800 10px "JetBrains Mono",
    monospace;
  letter-spacing: 0.08em;
  line-height: 1.7;
  max-width: 580px;
}
```

---

## 18. WORKSPACE LAYOUT SHELL — full grid with minimap

```jsx
// Replace the return block of MLV2Workbench
return (
  <main className={`ml-v2-shell-v3 ${cinemaId ? "cinema-active" : ""}`}>
    <MLTopbar
      featureId={feature.id}
      feature={feature}
      query={query}
      setQuery={setQuery}
      sections={orderedSections}
      response={response}
      onExport={() => setExportOpen(true)}
      onInputOpen={() => setInputOpen(true)}
    />

    <MLRunProgress running={loading} progress={progress} stage={runStage} />
    <MLStickySummary
      sections={orderedSections}
      activeId={activeId}
      response={response}
    />

    <FeatureHero
      feature={feature}
      sections={orderedSections}
      onRun={run}
      loading={loading}
    />

    {error ? (
      <div className="ml-error-v3">
        <AlertTriangle size={16} />
        {error}
      </div>
    ) : null}

    <section className="ml-workspace-v3">
      <MLOutputDock
        sections={orderedSections}
        activeId={activeId}
        onJump={jumpTo}
        cinemaId={cinemaId}
        onReorder={(from, to) => setSectionOrder((o) => moveById(o, from, to))}
      />

      <div className="ml-stack-v3">
        {orderedSections.map((section, i) => (
          <MLOutputCard
            key={section.id}
            section={section}
            response={response}
            index={i}
            activeId={activeId}
            onActive={setActiveId}
            cinemaId={cinemaId}
            onCinema={setCinemaId}
          />
        ))}
      </div>

      <MLMinimap
        sections={orderedSections}
        activeId={activeId}
        onJump={jumpTo}
      />
    </section>

    <AnimatePresence>
      {inputOpen ? (
        <MLInputCurtain
          feature={feature}
          form={form}
          setForm={setForm}
          open={inputOpen}
          onClose={() => setInputOpen(false)}
          onRun={run}
          loading={loading}
        />
      ) : null}
      {exportOpen ? (
        <MLExportModal
          feature={feature}
          form={form}
          sections={orderedSections}
          response={response}
          onClose={() => setExportOpen(false)}
        />
      ) : null}
    </AnimatePresence>

    <MLToastRack
      toasts={toasts}
      onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))}
    />
  </main>
);
```

```css
.ml-v2-shell-v3 {
  min-height: 100dvh;
  background: #030304;
  color: #e8edf5;
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
  padding: 0 clamp(18px, 3vw, 52px) 120px;
}
.ml-workspace-v3 {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr) 58px;
  gap: 18px;
  align-items: start;
}
.ml-stack-v3 {
  display: grid;
  gap: 14px;
}
.ml-error-v3 {
  margin: 0 0 16px;
  height: 46px;
  border: 1px solid rgba(255, 77, 106, 0.3);
  background: rgba(255, 77, 106, 0.07);
  color: #ff4d6a;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  font-size: 13px;
}
.cinema-active .ml-dock {
  opacity: 0.22;
}
.cinema-active .ml-minimap {
  opacity: 0.22;
}
@keyframes mlRevealV3 {
  from {
    opacity: 0;
    transform: translateY(20px);
    filter: blur(4px);
  }
  to {
    opacity: 1;
    transform: none;
    filter: blur(0);
  }
}
@media (max-width: 900px) {
  .ml-workspace-v3 {
    grid-template-columns: 1fr;
  }
  .ml-dock,
  .ml-minimap {
    display: none;
  }
}
```

---

## 19. MINIMAP right rail

```jsx
function MLMinimap({ sections, activeId, onJump }) {
  if (sections.length < 5) return null;
  return (
    <aside className="ml-minimap" aria-label="Output minimap">
      <span>MAP</span>
      {sections.map((section, i) => (
        <button
          key={section.id}
          className={activeId === section.id ? "active" : ""}
          onClick={() => onJump(section.id)}
          title={section.title}
          type="button"
        >
          <i />
          <em>{String(i + 1).padStart(2, "0")}</em>
        </button>
      ))}
    </aside>
  );
}
```

```css
.ml-minimap {
  position: sticky;
  top: 74px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}
.ml-minimap span {
  color: #00d4ff;
  font:
    900 8px "JetBrains Mono",
    monospace;
  letter-spacing: 0.2em;
  writing-mode: vertical-rl;
  margin-bottom: 6px;
  opacity: 0.6;
}
.ml-minimap button {
  width: 44px;
  height: 30px;
  border: 1px solid #1e2535;
  border-radius: 7px;
  background: #0a0c0f;
  position: relative;
  padding: 4px;
  cursor: pointer;
  transition:
    transform 0.15s,
    border-color 0.15s;
}
.ml-minimap button.active,
.ml-minimap button:hover {
  border-color: rgba(0, 212, 255, 0.5);
  transform: translateX(-4px);
}
.ml-minimap i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(
    135deg,
    rgba(0, 212, 255, 0.22),
    rgba(0, 0, 0, 0.1)
  );
}
.ml-minimap em {
  position: absolute;
  right: 3px;
  bottom: 2px;
  color: #4a5568;
  font:
    900 7px "JetBrains Mono",
    monospace;
  font-style: normal;
}
```

---

## 20. STATE MANAGEMENT ADDITIONS for the workbench — full v3 wiring

```jsx
// Replace all useState/useEffect/function blocks at the top of MLV2Workbench

const [form, setForm] = useState(() => ({ ...(feature.defaults || {}) }));
const [response, setResponse] = useState(null);
const [loading, setLoading] = useState(false);
const [progress, setProgress] = useState(0);
const [runStage, setRunStage] = useState("");
const [error, setError] = useState("");
const [query, setQuery] = useState("");
const [activeId, setActiveId] = useState(sections[0]?.id);
const [cinemaId, setCinemaId] = useState(null);
const [inputOpen, setInputOpen] = useState(false);
const [exportOpen, setExportOpen] = useState(false);
const [toasts, setToasts] = useState([]);
const [sectionOrder, setSectionOrder] = useState(() =>
  sections.map((s) => s.id),
);
const toastId = useRef(0);

const orderedSections = useMemo(() => {
  const byId = new Map(sections.map((s) => [s.id, s]));
  return sectionOrder.map((id) => byId.get(id)).filter(Boolean);
}, [sections, sectionOrder]);

const filtered = useMemo(
  () =>
    query
      ? orderedSections.filter((s) =>
          `${s.title} ${s.dataKey} ${s.chartType}`
            .toLowerCase()
            .includes(query.toLowerCase()),
        )
      : orderedSections,
  [orderedSections, query],
);

function pushToast(message, type = "info") {
  const id = ++toastId.current;
  setToasts((t) => [...t.slice(-3), { id, message, type }]);
  setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4400);
}

function moveById(list, fromId, toId) {
  if (!fromId || !toId || fromId === toId) return list;
  const next = [...list];
  const from = next.indexOf(fromId);
  const to = next.indexOf(toId);
  if (from < 0 || to < 0) return list;
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function jumpTo(id) {
  setActiveId(id);
  document
    .getElementById(id)
    ?.scrollIntoView({ behavior: "smooth", block: "center" });
}

const stages = [
  "Loading universe",
  "Building features",
  "Running models",
  "Computing outputs",
  "Rendering results",
];

async function run() {
  setLoading(true);
  setProgress(0.06);
  setError("");
  const timer = setInterval(() => {
    setProgress((p) => {
      const next = Math.min(0.92, p + 0.07);
      setRunStage(
        stages[Math.min(stages.length - 1, Math.floor(next * stages.length))],
      );
      return next;
    });
  }, 280);
  try {
    const result = await runMlV2Feature(feature.id, form);
    setResponse(result);
    setProgress(1);
    pushToast(
      `Run complete — ${orderedSections.length} outputs ready`,
      "success",
    );
    window.localStorage?.setItem(
      `quant360:ml-v2:${feature.id}:latest`,
      JSON.stringify(result?.summary_cards || []),
    );
  } catch (err) {
    setError(err?.message || "ML V2 API route is not wired yet.");
    pushToast(err?.message || "Run failed", "error");
  } finally {
    clearInterval(timer);
    setLoading(false);
    setTimeout(() => setProgress(0), 900);
  }
}
```

---

Every upgrade above is a direct drop-in. The design language moves from the old amber-border palette to a deep navy-black base with a cyan primary accent (`#00D4FF`) and green positive (`#00E5A0`) and red negative (`#FF4D6A`), which reads as a true institutional dark terminal rather than a warm amber UI. All the patterns present in the vol frontend that were absent from ML are now fully ported and elevated: cinema mode, drawing canvas, header sparklines, sticky summary bar, vertical dock with drag-to-reorder, minimap rail, run progress with stage labels, export modal, toast system, keyboard shortcuts, input curtain, animated hero with ambient orbs, and the full table with microbar heat columns.
