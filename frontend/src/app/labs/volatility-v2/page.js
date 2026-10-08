"use client";


import Link from "next/link";
import { animated, useSpring } from "@react-spring/web";
import { motion, useInView, useScroll, useTransform } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChevronDown, ExternalLink, Eye, X } from "lucide-react";
import * as d3Force from "d3-force";



const TOKENS = {
  page: "#050505",
  panel: "#0B0B0B",
  screen: "#0D0F11",
  raised: "#14110A",
  border: "#302613",
  borderSoft: "#1D1710",
  grid: "#2D2A24",
  accent: "#F5A400",
  text: "#F5F2EA",
  secondary: "#A8A197",
  muted: "#6E665B",
  green: "#22C55E",
  red: "#EF4444",
  blue: "#60A5FA",
  teal: "#14B8A6",
  purple: "#8B5CF6",
};















const clusters = [
  {
    id: "estimation-forecasting",
    ids: ["01", "02", "03"],
    label: "ESTIMATION",
    title: "Estimator & Forecasting Stack",
    description: "Start with the volatility surface you can compute from daily OHLCV. Estimators, GARCH density models, and HAR forecasts build the research-grade base layer.",
  },
  {
    id: "regime-premium",
    ids: ["04", "05"],
    label: "REGIME",
    title: "Regimes & Risk Premium",
    description: "Volatility is state-dependent. These modules identify regime probability, transition risk, VIX-vs-physical premium, and premium mean reversion.",
  },
  {
    id: "systemic-covariance",
    ids: ["06", "07", "08"],
    label: "SYSTEMIC",
    title: "Connectedness, DCC & Stress",
    description: "Risk fails through correlation and transmission. This layer maps spillovers, DCC covariance, crisis amplification, and reverse stress losses.",
  },
  {
    id: "portfolio-control",
    ids: ["09"],
    label: "CONTROL",
    title: "Portfolio Volatility Control",
    description: "Turn volatility intelligence into operational sizing, target-vol scaling, rebalancing recommendations, and budget breach logs.",
  },
];

const features = [
  {
    id: "01",
    tag: "MULTI-ESTIMATOR ENGINE",
    title: "Measure realized volatility without trusting one estimator.",
    description: "Compute close-to-close, Parkinson, Garman-Klass, Rogers-Satchell, and Yang-Zhang together. The engine highlights disagreement, liquidity noise, estimator efficiency, and cross-asset rankings.",
    bullets: ["Five daily OHLCV estimators", "Estimator disagreement band", "DM tournament and efficiency table", "Volatility calendar, cone, and signature plot", "Range correlation and opening-gap fragility"],
    visual: <EstimatorVisual />,
  },
  {
    id: "02",
    tag: "GARCH FAMILY SUITE",
    title: "Fit the volatility model family and know which density wins.",
    description: "Run the GARCH stack with term structure, residual adequacy, PIT diagnostics, VaR backtests, and model-confidence-set survivors. This is the model selection layer.",
    bullets: ["GARCH / EGARCH / GJR / APARCH / FIGARCH", "Term-structure forecast bands", "News impact curve", "Conditional VaR and PIT tests", "MCS survivor scoreboard"],
    visual: <GarchVisual />,
  },
  {
    id: "03",
    tag: "HAR FORECASTING",
    title: "Forecast realized volatility across horizons without losing jumps.",
    description: "HAR, LHAR, HAR-J, HAR-Leverage, ACSV-HAR, and HAR-X variants compete on forecast accuracy. Bootstrap bands show where confidence actually fades.",
    bullets: ["HAR parameter table", "Multi-horizon forecast chart", "Jump and leverage decomposition", "ACSV contribution", "Walk-forward accuracy"],
    visual: <HarVisual />,
  },
  {
    id: "04",
    tag: "REGIME DETECTION",
    title: "Track volatility states as probabilities, not labels.",
    description: "SJM, HMM, adaptive HMM, and rules-based signals produce a probability stack with transition alerts, duration survival, and method-divergence diagnostics.",
    bullets: ["Probabilistic regime timeline", "Current regime dashboard", "Transition heatmap", "EW-HMM adaptive timeline", "Smoothed vs filtered posterior"],
    visual: <RegimeVisual />,
  },
  {
    id: "05",
    tag: "VOL RISK PREMIUM",
    title: "See when implied volatility is overpaying or underpaying physical risk.",
    description: "The VRP monitor compares VIX-style implied expectation against physical volatility models, z-scores the spread, and tests return predictability across horizons.",
    bullets: ["VRP time series and z-score panel", "Physical expectation model comparison", "Return predictability regression", "Mean-reversion speed", "Term-structure decomposition"],
    visual: <VrpVisual />,
  },
  {
    id: "06",
    tag: "CONNECTEDNESS",
    title: "Find the asset transmitting volatility to the rest of the book.",
    description: "Diebold-Yilmaz generalized FEVD identifies total connectedness, net transmitters, receivers, frequency bands, and connectedness-at-risk alerts.",
    bullets: ["Total connectedness index", "Dynamic spillover network", "Pairwise FEVD heatmap", "Rolling to/from decomposition", "Connectedness-at-risk"],
    visual: <ConnectednessVisual />,
  },
  {
    id: "07",
    tag: "DCC ENGINE",
    title: "Upgrade covariance from static correlation to live multivariate risk.",
    description: "Sample, EWMA, Ledoit-Wolf, DCC-MLE, and DCC-MIDAS outputs show current correlation, crisis correlation, eigenvalues, condition number, and risk attribution.",
    bullets: ["DCC correlation heatmap", "Normal vs crisis triple matrix", "DCC-MIDAS long-run correlation", "Portfolio risk attribution", "Minimum torsion attribution"],
    visual: <DccVisual />,
  },
  {
    id: "08",
    tag: "STRESS ENGINE",
    title: "Replay volatility shocks and invert the loss scenario.",
    description: "Stress testing translates volatility shocks into P&L, VaR/CVaR, reverse stress, historical analogs, contagion IRFs, and adversarial scenarios.",
    bullets: ["Vol shock bar chart", "Portfolio P&L waterfall", "Reverse stress table", "Historical analog comparison", "IRF confidence bands"],
    visual: <StressVisual />,
  },
  {
    id: "09",
    tag: "VOL BUDGET",
    title: "Turn volatility forecasts into portfolio control.",
    description: "Portfolio volatility budget, target scaling, two-step rebalancing, Almgren-Chriss cost estimates, and historical target-vol backtests create the execution layer.",
    bullets: ["Vol dashboard and target gap gauge", "Budget attribution waterfall", "Scaling factor history", "Rebalancing recommendation", "Transaction cost netting"],
    visual: <BudgetVisual />,
  },
];

function CountUp({ value, suffix = "" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const { v } = useSpring({
    from: { v: 0 },
    to: { v: inView ? value : 0 },
    config: { tension: 60, friction: 22 },
  });

  return (
    <animated.span
      ref={ref}
      style={{
        fontVariantNumeric: "tabular-nums slashed-zero",
        fontFeatureSettings: '"tnum" 1, "zero" 1',
      }}
    >
      {v.to((number) => `${Math.round(number).toLocaleString()}${suffix}`)}
    </animated.span>
  );
}

function FeatureTabStrip() {
  const [active, setActive] = useState(clusters[0].id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible?.target?.id) return;
        setActive(visible.target.id);
        const cluster = clusters.find((item) => item.id === visible.target.id);
        if (cluster) window.dispatchEvent(new CustomEvent("volatility-cluster-active", { detail: { featureIds: cluster.ids } }));
      },
      { threshold: [0.22, 0.42], rootMargin: "-18% 0px -58% 0px" }
    );

    clusters.forEach((cluster) => {
      const el = document.getElementById(cluster.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <nav className="vol-tab-strip" aria-label="Volatility module clusters">
      {clusters.map((cluster) => (
        <a className={active === cluster.id ? "active" : ""} href={`#${cluster.id}`} key={cluster.id}>
          {cluster.label}
        </a>
      ))}
    </nav>
  );
}

function HeroNetwork() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const scale = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    canvas.width = width * scale;
    canvas.height = height * scale;
    ctx.scale(scale, scale);

    const nodes = Array.from({ length: 28 }, (_, index) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.34,
      vy: (Math.random() - 0.5) * 0.34,
      r: 2.5 + Math.random() * 3.2,
      hot: index < 4,
    }));

    let raf = 0;
    function draw() {
      ctx.clearRect(0, 0, width, height);
      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance < 130) {
            const alpha = (1 - distance / 130) * 0.18;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `${nodes[i].hot || nodes[j].hot ? "rgba(239,68,68," : "rgba(245,164,0,"}${alpha})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      nodes.forEach((node) => {
        const color = node.hot ? "rgba(239,68,68," : "rgba(245,164,0,";
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r + 7, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0.06)`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0.82)`;
        ctx.fill();
        node.x += node.vx;
        node.y += node.vy;
        if (node.x < 0 || node.x > width) node.vx *= -1;
        if (node.y < 0 || node.y > height) node.vy *= -1;
      });
      raf = requestAnimationFrame(draw);
    }

    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} className="hero-vol-canvas" aria-hidden="true" />;
}

function StatsBar() {
  const stats = [
    ["9", "Volatility Modules", 9, ""],
    ["5", "Estimator Family", 5, ""],
    ["2520", "Daily Lookback", 2520, "D"],
    ["DCC", "Covariance Engine", null, ""],
  ];
  return (
    <section className="vol-stats" id="vol-stats">
      {stats.map(([raw, label, value, suffix]) => (
        <div className="vol-stat" key={label}>
          <strong>{value == null ? raw : <CountUp value={value} suffix={suffix} />}</strong>
          <span>{label}</span>
        </div>
      ))}
    </section>
  );
}

function ClusterIntro({ cluster, index }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["10%", "-10%"]);

  return (
    <section className="vol-cluster" id={cluster.id} ref={ref}>
      <div className="vol-cluster-copy">
        <motion.span className="vol-cluster-ghost" style={{ y }} aria-hidden="true">
          0{index + 1}
        </motion.span>
        <p>{cluster.label}</p>
        <h2>{cluster.title}</h2>
        <span>{cluster.description}</span>
      </div>
      <div className="vol-cluster-pills">
        {cluster.ids.map((id) => {
          const feature = features.find((item) => item.id === id);
          return (
            <Link href={`/labs/volatility-v2/feature-${id}`} key={id}>
              <i />
              V{id} {feature?.tag}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function FeatureCard({ feature, flip, onPreview }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-15% 0px -15% 0px" });

  return (
    <motion.section
      ref={ref}
      className={`vol-feature-card ${flip ? "flip" : ""}`}
      initial={{ opacity: 0, y: 32 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="vol-feature-copy">
        <p>V{feature.id} · {feature.tag}</p>
        <h2>{feature.title}</h2>
        <span>{feature.description}</span>
        <ul>
          {feature.bullets.map((bullet, index) => (
            <motion.li
              animate={inView ? { opacity: 1, x: 0 } : {}}
              initial={{ opacity: 0, x: -12 }}
              key={bullet}
              transition={{ delay: 0.18 + index * 0.07, duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
            >
              {bullet}
            </motion.li>
          ))}
        </ul>
        <div className="vol-feature-actions">
          <Link href={`/labs/volatility-v2/feature-${feature.id}`}>Open Module <ExternalLink size={14} /></Link>
          <button onClick={() => onPreview(feature.id)} type="button"><Eye size={14} /> Preview</button>
        </div>
      </div>
      <motion.div
        className="vol-feature-visual"
        initial={{ opacity: 0, scale: 0.97 }}
        animate={inView ? { opacity: 1, scale: 1 } : {}}
        transition={{ delay: 0.12, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        {feature.visual}
        <div className="vol-watermark">V{feature.id}</div>
      </motion.div>
    </motion.section>
  );
}

function ChartShell({ title, children }) {
  return (
    <div className="vol-chart-shell">
      <header><span>{title}</span><b aria-hidden="true" /></header>
      <div>{children}</div>
    </div>
  );
}

function EstimatorVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function GarchVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function HarVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function RegimeVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function VrpVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function ConnectednessVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function DccVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function StressVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function BudgetVisual() { return <ChartShell title="Run required"><p>Run this feature to load observed backend results.</p></ChartShell>; }

function FooterCta() {
  return (
    <section className="vol-footer-cta">
      <p>VOLATILITY OPERATIONS</p>
      <h2>Ready to run the first volatility stack?</h2>
      <span>Start with V01 for clean realized volatility, V04 for regime state, or V07 if you are already managing a multi-asset risk book.</span>
      <div>
        <Link href="/labs/volatility-v2/feature-01">Start V01 Estimators</Link>
        <Link href="/labs/volatility-v2/feature-07">Open V07 DCC</Link>
      </div>
    </section>
  );
}

export default function VolatilityV2HomePage() {
  const [preview, setPreview] = useState(null);
  const blocks = useMemo(() => {
    const output = [];
    clusters.forEach((cluster) => {
      output.push({ type: "cluster", cluster });
      cluster.ids.forEach((id, localIndex) => output.push({ type: "feature", feature: features.find((item) => item.id === id), localIndex }));
    });
    return output;
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") setPreview(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const stack = document.querySelector(".vol-stack");
    if (!stack) return undefined;
    const onMove = (event) => {
      document.querySelectorAll(".vol-feature-card").forEach((card) => {
        const rect = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${event.clientX - rect.left}px`);
        card.style.setProperty("--my", `${event.clientY - rect.top}px`);
      });
    };
    stack.addEventListener("pointermove", onMove);
    return () => stack.removeEventListener("pointermove", onMove);
  }, []);

  return (
    <main className="vol-home">
      <section className="vol-hero">
        <HeroNetwork />
        <div className="vol-hero-content">
          <p><i /> ATLAS // VOLATILITY INTELLIGENCE</p>
          <h1>Institutional volatility<br /><span>command center.</span></h1>
          <h2>Nine daily-data volatility modules. From estimator disagreement and GARCH density checks to DCC covariance, stress testing, and portfolio risk budgets.</h2>
          <div className="vol-live-pills">
            <span><i className="green" /> V01 · Yang-Zhang 18.4%</span>
            <span><i /> V04 · Crisis prob 14%</span>
            <span><i className="red" /> V06 · Spillover 72</span>
          </div>
          <div className="vol-hero-actions">
            <a href="#estimation-forecasting">Explore modules</a>
            <Link href="/labs/volatility-v2/feature-01">Open V01 live shell</Link>
          </div>
        </div>
        <button className="vol-chevron" onClick={() => document.getElementById("vol-stats")?.scrollIntoView({ behavior: "smooth" })} type="button" aria-label="Scroll to stats">
          <ChevronDown size={28} />
        </button>
      </section>

      <StatsBar />
      <FeatureTabStrip />

      <div className="vol-stack">
        {blocks.map((block) => {
          if (block.type === "cluster") {
            const clusterIndex = clusters.findIndex((cluster) => cluster.id === block.cluster.id);
            return <ClusterIntro cluster={block.cluster} index={clusterIndex} key={block.cluster.id} />;
          }
          return <FeatureCard feature={block.feature} flip={block.localIndex % 2 === 1} key={block.feature.id} onPreview={setPreview} />;
        })}
      </div>

      <FooterCta />

      {preview ? (
        <div className="vol-preview-overlay" role="dialog" aria-modal="true">
          <header>
            <span>Preview · V{preview}</span>
            <button onClick={() => setPreview(null)} type="button"><X size={18} /></button>
          </header>
          <iframe src={`/labs/volatility-v2/feature-${preview}`} title={`Volatility V2 feature ${preview} preview`} />
        </div>
      ) : null}

      <style jsx global>{`
        html { scroll-behavior: smooth; }
        .vol-home {
          min-height: 100dvh;
          background: #050505;
          color: ${TOKENS.text};
          overflow-x: hidden;
        }

        .vol-home ::selection { background: rgba(245,164,0,.26); color: #fff7e5; }

        .vol-hero {
          min-height: 100dvh;
          position: relative;
          display: grid;
          place-items: center;
          isolation: isolate;
          border-bottom: 1px solid ${TOKENS.borderSoft};
        }

        .vol-hero::before {
          content: "";
          position: absolute;
          inset: 0;
          background:
            radial-gradient(ellipse 55% 45% at 20% 60%, rgba(245,164,0,.07) 0%, transparent 70%),
            radial-gradient(ellipse 40% 55% at 80% 20%, rgba(245,164,0,.05) 0%, transparent 65%),
            radial-gradient(ellipse 70% 35% at 50% 0%, rgba(245,164,0,.09) 0%, transparent 60%);
          pointer-events: none;
          z-index: 0;
        }

        .vol-hero::after {
          content: "";
          position: absolute;
          inset: auto 0 0;
          height: 40%;
          background: linear-gradient(180deg, transparent, rgba(5,5,5,.85));
          z-index: 1;
          pointer-events: none;
        }

        .hero-vol-canvas {
          position: absolute;
          right: 0;
          top: 0;
          width: min(560px, 42vw);
          height: 100%;
          opacity: .56;
          z-index: 0;
          pointer-events: none;
        }

        .vol-hero-content {
          position: relative;
          z-index: 2;
          width: min(1040px, calc(100vw - 32px));
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 120px 0 80px;
        }

        .vol-hero-content > p {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          margin: 0 0 28px;
          color: ${TOKENS.accent};
          font-size: 11px;
          font-weight: 850;
          letter-spacing: .38em;
          text-transform: uppercase;
        }

        .vol-hero-content > p i {
          width: 1px;
          height: 16px;
          background: ${TOKENS.accent};
          display: inline-block;
        }

        .vol-hero h1 {
          margin: 0;
          color: ${TOKENS.text};
          font-family: Georgia, "Times New Roman", serif;
          font-size: clamp(56px, 8vw, 118px);
          line-height: .87;
          letter-spacing: -.055em;
        }

        .vol-hero h1 span {
          background: linear-gradient(135deg, #F5A400 0%, #FFD166 45%, #F5A400 100%);
          background-clip: text;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .vol-hero h2 {
          max-width: 760px;
          margin: 34px 0 0;
          color: ${TOKENS.secondary};
          font-size: clamp(17px, 1.8vw, 22px);
          font-weight: 450;
          line-height: 1.58;
        }

        .vol-live-pills {
          display: flex;
          justify-content: center;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 34px;
        }

        .vol-live-pills span {
          height: 34px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 0 15px;
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 999px;
          background: rgba(12,12,12,.72);
          color: ${TOKENS.secondary};
          font-family: "JetBrains Mono", monospace;
          font-size: 11px;
          font-weight: 850;
          letter-spacing: .08em;
        }

        .vol-live-pills i {
          width: 7px;
          height: 7px;
          border-radius: 999px;
          background: ${TOKENS.accent};
          box-shadow: 0 0 14px currentColor;
        }

        .vol-live-pills .green { background: ${TOKENS.green}; }
        .vol-live-pills .red { background: ${TOKENS.red}; }

        .vol-hero-actions {
          display: flex;
          justify-content: center;
          gap: 12px;
          flex-wrap: wrap;
          margin-top: 50px;
        }

        .vol-hero-actions a,
        .vol-footer-cta a,
        .vol-feature-actions a,
        .vol-feature-actions button {
          height: 48px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 0 22px;
          border: 1px solid ${TOKENS.border};
          border-radius: 8px;
          background: rgba(20,17,10,.82);
          color: ${TOKENS.text};
          text-decoration: none;
          font-size: 13px;
          font-weight: 850;
          cursor: pointer;
          transition: transform 150ms ease, border-color 150ms ease, background 150ms ease, color 150ms ease;
        }

        .vol-hero-actions a:first-child,
        .vol-footer-cta a:first-child {
          border-color: ${TOKENS.accent};
          background: ${TOKENS.accent};
          color: #050505;
        }

        .vol-hero-actions a:hover,
        .vol-footer-cta a:hover,
        .vol-feature-actions a:hover,
        .vol-feature-actions button:hover {
          transform: translateY(-2px);
          border-color: ${TOKENS.accent};
          color: ${TOKENS.accent};
        }

        .vol-hero-actions a:first-child:hover,
        .vol-footer-cta a:first-child:hover {
          color: #050505;
          box-shadow: 0 18px 44px rgba(245,164,0,.2);
        }

        .vol-chevron {
          position: absolute;
          bottom: 40px;
          left: 50%;
          transform: translateX(-50%);
          border: 0;
          background: transparent;
          color: ${TOKENS.muted};
          cursor: pointer;
          animation: volChevronPulse 2s ease-in-out infinite;
        }

        @keyframes volChevronPulse {
          0%, 100% { opacity: .35; transform: translateX(-50%) translateY(0); }
          50% { opacity: .8; transform: translateX(-50%) translateY(8px); }
        }

        .vol-stats {
          height: 84px;
          display: grid;
          grid-template-columns: repeat(5, 1fr);
          border-top: 1px solid ${TOKENS.borderSoft};
          border-bottom: 1px solid ${TOKENS.borderSoft};
          background: #090806;
          box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
        }

        .vol-stat {
          display: grid;
          place-items: center;
          align-content: center;
          gap: 5px;
          border-left: 1px solid ${TOKENS.borderSoft};
        }

        .vol-stat:first-child { border-left: 0; }
        .vol-stat strong {
          color: ${TOKENS.text};
          font-family: "JetBrains Mono", monospace;
          font-size: 27px;
          font-weight: 950;
          font-variant-numeric: tabular-nums slashed-zero;
        }

        .vol-stat span {
          color: ${TOKENS.muted};
          font-size: 10px;
          font-weight: 850;
          letter-spacing: .18em;
          text-transform: uppercase;
        }

        .vol-tab-strip {
          position: sticky;
          top: 0;
          z-index: 30;
          height: 48px;
          display: flex;
          align-items: center;
          gap: 0;
          overflow-x: auto;
          scrollbar-width: none;
          padding: 0 clamp(18px, 4vw, 56px);
          border-bottom: 1px solid ${TOKENS.borderSoft};
          background: rgba(8, 7, 6, .9);
          backdrop-filter: blur(18px);
        }

        .vol-tab-strip::-webkit-scrollbar { display: none; }

        .vol-tab-strip a {
          height: 100%;
          display: inline-flex;
          align-items: center;
          padding: 0 18px;
          border-bottom: 2px solid transparent;
          color: ${TOKENS.muted};
          text-decoration: none;
          font-size: 12px;
          font-weight: 900;
          letter-spacing: .12em;
          white-space: nowrap;
        }

        .vol-tab-strip a.active {
          color: ${TOKENS.text};
          border-bottom-color: ${TOKENS.accent};
        }

        .vol-stack {
          width: min(1440px, calc(100vw - 32px));
          margin: 0 auto;
          padding: 2px 0 0;
          counter-reset: vol-cluster;
        }

        .vol-cluster {
          min-height: 280px;
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(320px, .86fr);
          gap: 44px;
          align-items: center;
          padding: 70px clamp(18px, 4vw, 56px);
          border-top: 1px solid ${TOKENS.borderSoft};
          background: #050505;
          box-shadow: inset 0 1px 0 rgba(255,255,255,.035);
          counter-increment: vol-cluster;
        }

        .vol-cluster-copy {
          position: relative;
          overflow: hidden;
        }

        .vol-cluster-ghost {
          position: absolute;
          top: -.14em;
          left: -.08em;
          z-index: 0;
          color: transparent;
          -webkit-text-stroke: 1px rgba(245, 164, 0, .075);
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: clamp(110px, 16vw, 210px);
          font-weight: 950;
          line-height: 1;
          pointer-events: none;
          user-select: none;
          will-change: transform;
        }

        .vol-cluster-copy > *:not(.vol-cluster-ghost) {
          position: relative;
          z-index: 1;
        }

        .vol-cluster p,
        .vol-footer-cta p {
          margin: 0 0 16px;
          color: ${TOKENS.accent};
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .24em;
        }

        .vol-cluster h2,
        .vol-footer-cta h2 {
          margin: 0;
          color: ${TOKENS.text};
          font-size: clamp(36px, 4.6vw, 58px);
          line-height: .95;
          letter-spacing: -.035em;
        }

        .vol-cluster span,
        .vol-footer-cta > span {
          display: block;
          max-width: 620px;
          margin-top: 22px;
          color: ${TOKENS.secondary};
          font-size: 16px;
          line-height: 1.75;
        }

        .vol-cluster-pills {
          display: flex;
          justify-content: flex-end;
          flex-wrap: wrap;
          gap: 10px;
        }

        .vol-cluster-pills a {
          min-height: 42px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 0 14px;
          border: 1px solid ${TOKENS.border};
          border-radius: 999px;
          background: rgba(20,17,10,.7);
          color: ${TOKENS.secondary};
          text-decoration: none;
          font-family: "JetBrains Mono", monospace;
          font-size: 11px;
          font-weight: 850;
        }

        .vol-cluster-pills i {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: ${TOKENS.accent};
        }

        .vol-feature-card {
          position: relative;
          min-height: 650px;
          display: grid;
          grid-template-columns: .45fr .55fr;
          gap: 48px;
          align-items: center;
          padding: clamp(28px, 4.6vw, 66px);
          margin-top: 2px;
          border: 1px solid transparent;
          border-radius: 16px;
          background:
            linear-gradient(#090908, #090908) padding-box,
            linear-gradient(to bottom right, rgba(245,164,0,.18), rgba(245,164,0,.04) 40%, rgba(245,164,0,.04) 60%, rgba(245,164,0,.14)) border-box;
          overflow: hidden;
          transition: border-color 180ms ease;
        }

        .vol-feature-card::before {
          content: "";
          position: absolute;
          inset: -1px;
          border-radius: inherit;
          background: radial-gradient(600px circle at var(--mx, -999px) var(--my, -999px), rgba(245,164,0,.13), transparent 40%);
          z-index: 0;
          pointer-events: none;
          transition: opacity 120ms ease;
        }

        .vol-feature-card > * {
          position: relative;
          z-index: 1;
        }

        .vol-feature-card:hover { border-color: rgba(245,164,0,.36); }
        .vol-feature-card.flip .vol-feature-copy { order: 2; }
        .vol-feature-card.flip .vol-feature-visual { order: 1; }

        .vol-feature-copy p {
          margin: 0 0 18px;
          color: ${TOKENS.accent};
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .2em;
        }

        .vol-feature-copy h2 {
          margin: 0;
          color: ${TOKENS.text};
          font-size: clamp(34px, 4.1vw, 54px);
          line-height: 1.02;
          letter-spacing: -.035em;
        }

        .vol-feature-copy > span {
          display: block;
          max-width: 560px;
          margin-top: 22px;
          color: ${TOKENS.secondary};
          font-size: 16px;
          line-height: 1.74;
        }

        .vol-feature-copy ul {
          list-style: none;
          padding: 0;
          margin: 26px 0 0;
          display: grid;
          gap: 12px;
          max-width: 580px;
        }

        .vol-feature-copy li {
          display: flex;
          gap: 12px;
          color: ${TOKENS.text};
          font-size: 14px;
          line-height: 1.65;
        }

        .vol-feature-copy li::before {
          content: "";
          width: 5px;
          height: 5px;
          margin-top: 10px;
          flex: 0 0 auto;
          background: ${TOKENS.accent};
        }

        .vol-feature-actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          margin-top: 32px;
        }

        .vol-feature-actions button {
          font-family: inherit;
        }

        .vol-feature-visual {
          position: relative;
          min-height: 430px;
          display: grid;
          place-items: center;
          padding: 24px;
          border: 1px solid ${TOKENS.border};
          border-radius: 14px;
          background:
            radial-gradient(circle at 30% 20%, rgba(245,164,0,.08), transparent 38%),
            ${TOKENS.screen};
          box-shadow:
            0 0 80px rgba(245,164,0,.06),
            inset 0 1px 0 rgba(255,255,255,.05),
            inset 0 0 0 1px rgba(255,255,255,.02);
          overflow: hidden;
          cursor: crosshair;
        }

        .vol-feature-visual::after {
          content: "";
          position: absolute;
          inset: 0;
          background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px);
          background-size: 42px 42px;
          pointer-events: none;
          opacity: .55;
        }

        .vol-watermark {
          position: absolute;
          right: 22px;
          bottom: 12px;
          color: ${TOKENS.text};
          opacity: .045;
          font-size: 76px;
          font-weight: 950;
          letter-spacing: -.06em;
        }

        .vol-chart-shell {
          position: relative;
          z-index: 1;
          width: 100%;
          height: 100%;
          display: grid;
          grid-template-rows: 38px 1fr;
          border: 1px solid #1F1C15;
          border-radius: 10px;
          background: #080807;
          overflow: hidden;
        }

        .vol-chart-shell header {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 0 14px;
          border-bottom: 1px solid #1A1710;
          background: #0C0B08;
        }

        .vol-chart-shell header::before {
          content: "";
          width: 10px;
          height: 10px;
          flex: 0 0 auto;
          margin-right: 42px;
          border-radius: 50%;
          background: #3A3530;
          box-shadow: 18px 0 0 #3A3530, 36px 0 0 #3A3530;
        }

        .vol-chart-shell header span {
          flex: 1;
          color: #5A5448;
          font-family: "JetBrains Mono", "IBM Plex Mono", Consolas, monospace;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: .12em;
          text-transform: uppercase;
        }

        .vol-chart-shell header b {
          width: 7px;
          height: 7px;
          flex: 0 0 auto;
          border-radius: 50%;
          background: ${TOKENS.accent};
          box-shadow: 0 0 8px rgba(245,164,0,.6);
          animation: chartPulse 2.8s ease-in-out infinite;
        }

        .vol-chart-shell > div {
          padding: 10px 4px 4px;
        }

        @keyframes chartPulse {
          0%, 100% { opacity: .5; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.3); }
        }

        .vol-stat strong,
        .vol-chart-shell,
        .vol-strip-pill span,
        .vol-live-pills span,
        .vol-cmd-badge,
        .vol-signature-plot,
        .vol-vrp-scatter,
        .vol-budget-row {
          font-variant-numeric: tabular-nums slashed-zero;
          font-feature-settings: "tnum" 1, "zero" 1;
        }

        .vol-network-preview {
          width: 100%;
          height: 330px;
        }

        .vol-svg-wrap,
        .vol-regime-calendar,
        .vol-dcc-wrap {
          width: 100%;
          min-height: 330px;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow-x: auto;
          scrollbar-width: none;
        }

        .vol-svg-wrap::-webkit-scrollbar,
        .vol-regime-calendar::-webkit-scrollbar,
        .vol-dcc-wrap::-webkit-scrollbar { display: none; }

        .vol-signature-plot,
        .vol-regime-calendar svg,
        .vol-dcc-wrap svg {
          width: min(100%, 460px);
          min-width: 360px;
        }

        .vol-dcc-wrap circle {
          cursor: crosshair;
          transition: opacity 120ms ease, r 120ms ease, stroke 120ms ease;
        }

        .vol-budget-bullets {
          width: min(460px, 100%);
          margin: auto;
          display: grid;
          gap: 18px;
          padding: 18px 6px;
        }

        .vol-budget-row {
          display: grid;
          grid-template-columns: 46px 1fr 44px;
          align-items: center;
          gap: 12px;
          color: ${TOKENS.secondary};
          font-family: "JetBrains Mono", monospace;
          font-size: 11px;
          font-weight: 900;
        }

        .vol-budget-row > div {
          position: relative;
          height: 15px;
          border: 1px solid rgba(245,164,0,.16);
          border-radius: 999px;
          background: rgba(255,255,255,.035);
          overflow: hidden;
        }

        .vol-budget-row i {
          position: absolute;
          inset: 0 auto 0 0;
          border-radius: inherit;
          opacity: .82;
        }

        .vol-budget-row b {
          position: absolute;
          top: -4px;
          bottom: -4px;
          width: 2px;
          background: ${TOKENS.green};
          box-shadow: 0 0 10px rgba(34,197,94,.32);
        }

        .vol-budget-row strong {
          text-align: right;
          font-size: 11px;
        }

        .vol-footer-cta {
          min-height: 430px;
          display: grid;
          place-items: center;
          text-align: center;
          padding: 90px 20px 130px;
          background: radial-gradient(ellipse 50% 40% at 50% 0%, rgba(245,164,0,.1), transparent 70%), #050505;
        }

        .vol-footer-cta > div {
          display: flex;
          justify-content: center;
          gap: 12px;
          flex-wrap: wrap;
          margin-top: 34px;
        }

        .vol-preview-overlay {
          position: fixed;
          inset: 22px;
          z-index: 110;
          display: grid;
          grid-template-rows: 50px 1fr;
          border: 1px solid rgba(245,164,0,.38);
          border-radius: 18px;
          background: #050505;
          box-shadow: 0 30px 120px rgba(0,0,0,.72);
          overflow: hidden;
        }

        .vol-preview-overlay header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px 0 18px;
          border-bottom: 1px solid ${TOKENS.borderSoft};
          color: ${TOKENS.accent};
          font-size: 12px;
          font-weight: 900;
          letter-spacing: .14em;
        }

        .vol-preview-overlay button {
          width: 34px;
          height: 34px;
          border: 1px solid ${TOKENS.border};
          border-radius: 8px;
          background: ${TOKENS.raised};
          color: ${TOKENS.text};
          cursor: pointer;
        }

        .vol-preview-overlay iframe {
          width: 100%;
          height: 100%;
          border: 0;
          background: #050505;
        }

        @media (max-width: 1120px) {
          .hero-vol-canvas { display: none; }
          .vol-feature-card,
          .vol-feature-card.flip {
            grid-template-columns: 1fr;
          }
          .vol-feature-card.flip .vol-feature-copy,
          .vol-feature-card.flip .vol-feature-visual {
            order: initial;
          }
          .vol-cluster {
            grid-template-columns: 1fr;
          }
          .vol-cluster-pills {
            justify-content: flex-start;
          }
        }

        @media (max-width: 760px) {
          .vol-stats {
            height: auto;
            grid-template-columns: 1fr 1fr;
          }
          .vol-stat {
            min-height: 76px;
            border-top: 1px solid ${TOKENS.borderSoft};
          }
          .vol-feature-card {
            padding: 24px 18px;
          }
          .vol-feature-visual {
            min-height: 360px;
            padding: 16px;
          }
          .vol-preview-overlay {
            inset: 8px;
          }
        }
      `}</style>
    </main>
  );
}
