"use client";

import Link from "next/link";
import * as d3 from "d3";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Label,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronDown, Download, ExternalLink, Eye, X } from "lucide-react";

const TOKENS = {
  page: "#050505",
  panel: "#0B0B0B",
  elevated: "#15120B",
  border: "#2E2618",
  borderSoft: "#1C1710",
  accent: "#F5A400",
  text: "#F4F1EA",
  secondary: "#A8A29A",
  muted: "#6F675C",
  green: "#3FB950",
  red: "#F85149",
  amber: "#F5A400",
  purple: "#A371F7",
};

const axis = {
  tick: { fill: TOKENS.secondary, fontSize: 11, fontFamily: "JetBrains Mono, IBM Plex Mono, Consolas, monospace" },
  axisLine: false,
  tickLine: false,
};

const tooltip = {
  background: "#15120B",
  border: "1px solid #2E2618",
  borderRadius: 6,
  color: "#F4F1EA",
  fontSize: 12,
};

function pctWave(length, start, drift, amp, phase = 0) {
  return Array.from({ length }, (_, index) => ({
    label: String(2015 + Math.floor((index / length) * 10)),
    value: Math.max(4, Math.min(96, start + drift * index + Math.sin(index / 2.4 + phase) * amp + Math.cos(index / 5) * amp * 0.4)),
  }));
}

const f01History = pctWave(50, 54, -0.42, 10).map((row, index) => ({ ...row, year: index === 49 ? "TODAY" : row.label }));
const f04Regimes = Array.from({ length: 60 }, (_, index) => {
  const transition = 0.22 + Math.sin(index / 7) * 0.04 + Math.max(0, index - 49) * 0.007;
  const stress = 0.08 + Math.cos(index / 8) * 0.03 + Math.max(0, index - 49) * 0.018;
  const crisis = Math.max(0, Math.sin((index - 8) / 9) * 0.018);
  const expansion = Math.max(0.42, 1 - transition - stress - crisis);
  const total = expansion + transition + stress + crisis;
  return { month: `M${index + 1}`, expansion: expansion / total, transition: transition / total, stress: stress / total, crisis: crisis / total };
});
const decayData = [1, 5, 21, 63, 126, 252].map((h) => ({
  horizon: h,
  value: 0.062 * Math.exp(-h / 182) + 0.006,
  momentum: 0.071 * Math.exp(-h / 31) + 0.002,
  quality: 0.048 * Math.exp(-h / 235) + 0.008,
}));
const equityData = Array.from({ length: 120 }, (_, index) => {
  const t = index / 119;
  const drawdown = index > 77 && index < 91 ? -0.184 * Math.sin(((index - 77) / 14) * Math.PI) : -0.02 * Math.max(0, Math.sin(index / 8));
  return {
    month: `${2015 + Math.floor(index / 12)}.${String((index % 12) + 1).padStart(2, "0")}`,
    gross: 100 * (1 + 3.4 * t + Math.sin(index / 8) * 0.18),
    net: 100 * (1 + 2.87 * t + Math.sin(index / 8 + 0.4) * 0.14),
    benchmark: 100 * (1 + 1.8 * t + Math.sin(index / 10) * 0.09),
    drawdown,
  };
});
const capacityData = [
  { aum: "10M", alpha: 142 },
  { aum: "100M", alpha: 118 },
  { aum: "500M", alpha: 76 },
  { aum: "1B", alpha: 42 },
  { aum: "2B", alpha: 8 },
  { aum: "3B", alpha: -24 },
  { aum: "10B", alpha: -98 },
];
const frontierData = Array.from({ length: 50 }, (_, index) => {
  const vol = 6 + (index / 49) * 12;
  return { vol, ret: 4 + Math.pow((vol - 6) / 12, 1.45) * 10 };
});
const dnaData = [
  ["IC", 78, 82],
  ["ICIR", 71, 76],
  ["Half-Life", 85, 28],
  ["Crowding", 34, 22],
  ["Sector Purity", 62, 71],
  ["Regime Stability", 58, 44],
  ["Independence", 81, 68],
  ["Purity", 74, 61],
].map(([axisName, value, momentum]) => ({ axis: axisName, value, momentum }));

const clusters = [
  {
    id: "valuation-exposure",
    ids: ["01", "02", "03"],
    title: "Valuation & Exposure",
    description: "Start with what the factor is worth, what your book owns, and where active return came from. These modules convert cross-sectional data into PM-ready diagnostics.",
    features: ["F01 Valuation", "F02 Exposure", "F03 Attribution"],
  },
  {
    id: "regime-timing",
    ids: ["04", "05"],
    title: "Regime & Timing",
    description: "Factor performance is state-dependent. This cluster handles regime probabilities, transition risk, signal half-life, and the timing window where alpha still survives.",
    features: ["F04 Regimes", "F05 Decay"],
  },
  {
    id: "risk-crowding",
    ids: ["06", "08", "11"],
    title: "Risk & Crowding",
    description: "Crowded books do not fail linearly. These modules show concentration, liquidity stress, correlation spikes, and scenario losses before they become forced exits.",
    features: ["F06 Crowding", "F08 Covariance", "F11 Stress Test"],
  },
  {
    id: "portfolio-capacity",
    ids: ["07", "09", "10"],
    title: "Portfolio & Capacity",
    description: "A signal becomes institutional only when it can be traded, sized, and constrained. This cluster handles backtesting, capacity, and optimal construction.",
    features: ["F07 Backtest", "F09 Capacity", "F10 Optimizer"],
  },
  {
    id: "signal-intelligence",
    ids: ["12", "13", "14"],
    title: "Signal Intelligence",
    description: "The final layer classifies what the factor is, monitors whether it is degrading, and packages the result into allocator-ready transparency materials.",
    features: ["F12 Factor DNA", "F13 Signal Health", "F14 DDQ Report"],
  },
];

const features = [
  {
    id: "01",
    tag: "VALUATION INTELLIGENCE",
    headline: "Is Value cheap or\nexpensive right now?",
    description: "The Factor Valuation Spread Monitor answers the question every PM checks before putting on a factor trade: where does today's valuation spread sit relative to its own 10-year history? Bloomberg gives you raw data. This gives you the answer, expressed as a historical percentile with an implied 12-month expected return attached to it.",
    bullets: [
      "Current valuation spread percentile for Value, Momentum, Quality, Low-Vol, Size, Growth, and custom factors",
      "Historical percentile computed against 10 years of daily data, expressed on a 0-100 dial",
      "Regression-implied 12-month expected return with a 90% confidence interval",
      "Factor valuation correlation matrix showing which factors are simultaneously stretched",
      "Cross-sector spread table identifying pervasive versus concentrated cheapness",
      "Crisis anchor annotations for GFC, COVID, and Liberation Day percentile levels",
    ],
    visual: <F01Visual />,
  },
  {
    id: "02",
    tag: "PORTFOLIO X-RAY",
    headline: "What factor bets is your\nportfolio actually running?",
    description: "Every portfolio has factor exposures whether the manager intends them or not. The exposure decomposition runs characteristic-based and return-based methodologies together and reports where they diverge. The tilt summary translates the z-score output into language a PM can use in an allocator meeting.",
    bullets: [
      "Characteristic-based and return-based exposures with divergence flagging",
      "Active exposures relative to any benchmark showing exactly what bets are active",
      "Holdings-level heatmap across stocks and factors with color-coded z-scores",
      "Unintended exposure detector for active loadings above 0.4 sigma",
      "Plain-language tilt summary generated from z-score output",
      "Rolling exposure time series showing how factor loading evolved month by month",
    ],
    visual: <ExposureBars />,
  },
  {
    id: "03",
    tag: "PERFORMANCE DECOMPOSITION",
    headline: "Where did your returns\nactually come from?",
    description: "Brinson-Fachler attribution crossed with factor decomposition answers the Monday morning question. Active return is decomposed into allocation, selection, and interaction effects, then aggregated into a waterfall that shows whether performance came from factor tilts, stock selection, or timing.",
    bullets: [
      "Full Brinson-Fachler allocation, selection, and interaction by GICS sector",
      "Factor contribution table with exposure times return and t-statistics",
      "Information ratio split between factor harvesting and stock selection skill",
      "Carryover effect report from prior rebalancing decisions",
      "Rolling 12-month and 36-month IR for skill stability",
      "Best and worst attribution periods with dominant driver named",
    ],
    visual: <WaterfallVisual data={[["Market", 4.2], ["Value", 1.8], ["Momentum", 0.9], ["Quality", -0.4], ["Low-Vol", 0.3], ["Selection", 1.1], ["Interaction", -0.3], ["Carryover", 0.6], ["Total", 8.2]]} />,
  },
  {
    id: "04",
    tag: "REGIME INTELLIGENCE",
    headline: "Which macro regime are\nyou actually in right now?",
    description: "A binary recession or expansion label is not a regime model. The probabilistic regime timeline outputs a probability vector at every date, combining macro rules, HMM factor behavior, and covariance clustering into a composite probability.",
    bullets: [
      "Three parallel regime detection methods combined by log-space averaging",
      "Hidden Markov Model fitted directly to factor return vectors",
      "Continuous probability timeline rather than hard state labels",
      "Factor return heatmap by regime with monthly return and Sharpe",
      "Regime transition matrix over 1, 3, and 6 months",
      "Factor timing regression showing current buy or sell signals",
    ],
    visual: <RegimeVisual />,
  },
  {
    id: "05",
    tag: "SIGNAL DECAY",
    headline: "How long does your\nfactor's edge actually last?",
    description: "Factor alpha decays. The IC decay curve traces the rank correlation between factor scores and forward returns from T+1 to T+252 trading days. Fitted decay models and half-life estimates convert signal persistence into a rebalancing decision.",
    bullets: [
      "IC decay curves for up to 10 factors with bootstrap confidence bands",
      "Linear, exponential, and hyperbolic fits compared by R-squared",
      "Half-life in trading days and calendar weeks with bootstrap interval",
      "Optimal rebalancing frequency from cost-benefit peak",
      "Rolling half-life showing post-2015 decay acceleration",
      "Post-2015 acceleration test with statistical significance",
    ],
    visual: <DecayVisual />,
  },
  {
    id: "06",
    tag: "CROWDING INTELLIGENCE",
    headline: "Know when your factor trade\nis too crowded to enter",
    description: "Crowding is the primary failure mode for systematic equity strategies. The Crowding Monitor builds a composite score from valuation stretch, autocorrelation, concentration, and liquidity deterioration, then expresses it as a historical percentile.",
    bullets: [
      "Composite crowding score across four independent pressure signals",
      "10-year percentile with full density distribution",
      "Empirical crash probability by horizon with Bayesian credible intervals",
      "Annotated time series around major quant unwind episodes",
      "Deleveraging risk from turnover, concentration, and inverse liquidity",
      "Four-axis radar chart showing the dominant crowding driver",
    ],
    visual: <CrowdingVisual />,
  },
  {
    id: "08",
    tag: "RISK ARCHITECTURE",
    headline: "Factor correlations spike in crises.\nSee which ones and by how much.",
    description: "The covariance matrix changes dramatically between normal and crisis periods. Crowding causes correlations to spike across factors, so normal-period matrices often underestimate tail risk. The comparison heatmap makes that risk visible.",
    bullets: [
      "Sample, EWMA, Ledoit-Wolf, and DCC-GARCH estimator comparison",
      "Normal versus crisis heatmaps with delta amplification matrix",
      "Eigenvalue decomposition showing one-risk dominance",
      "Rolling DCC correlation for any factor pair",
      "Portfolio risk decomposition into variance and covariance effects",
      "Minimum variance factor combination for correlation risk reduction",
    ],
    visual: <CovarianceVisual />,
  },
  {
    id: "11",
    tag: "SCENARIO ANALYSIS",
    headline: "What would your portfolio lose\nin the next Liberation Day?",
    description: "Forward stress testing replays historical scenarios against current exposures. Reverse stress testing asks what factor combination would cause a chosen loss. The contagion model shows which factors follow after a factor shock.",
    bullets: [
      "Preset historical shocks including GFC, COVID, Rate Shock, Liberation Day, and quant unwind",
      "Reverse stress scenario for a user-defined loss threshold",
      "VAR contagion impulse response at 1D, 5D, 10D, and 21D",
      "Mahalanobis matching against historical periods",
      "Multi-scenario comparison across six scenarios",
      "Hedging recommendation to immunize against a stress scenario",
    ],
    visual: <WaterfallVisual data={[["Market", -6.2], ["Value", -1.8], ["Momentum", -4.1], ["Quality", -0.9], ["Low-Vol", 2.1], ["Size", -1.4], ["Selection", -0.8], ["Total", -13.1]]} />,
  },
  {
    id: "07",
    tag: "STRATEGY VALIDATION",
    headline: "The only backtest that tells you\nwhat survives transaction costs",
    description: "A gross return backtest is a hypothesis. A net return backtest with realistic implementation shortfall is evidence. This engine models explicit costs, market impact, and timing cost, then shows how much result came from timing luck.",
    bullets: [
      "Three-component implementation shortfall with explicit, impact, and timing cost",
      "250 randomized rebalancing offsets showing timing-luck sensitivity",
      "Quintile monotonicity chart as the primary empirical validity test",
      "Walk-forward factor weight optimization applied out-of-sample",
      "AUM capacity constraint before costs consume the gross premium",
      "Full statistics table including Sharpe, Sortino, Calmar, drawdown, and CVaR",
    ],
    visual: <BacktestVisual />,
  },
  {
    id: "09",
    tag: "CAPACITY INTELLIGENCE",
    headline: "How much AUM can your strategy\nabsorb before alpha disappears?",
    description: "Capacity distinguishes a research insight from a deployable strategy. As AUM grows, impact costs grow superlinearly until they consume the entire gross premium. The capacity ceiling is where net alpha crosses zero.",
    bullets: [
      "AUM sweep from $1M to $10B on a log scale",
      "Capacity ceiling where net alpha reaches zero",
      "Optimal AUM near half of the ceiling where net alpha is maximized",
      "Slippage table at $10M, $100M, $1B, and $10B",
      "Time-to-liquidate at each AUM level under ADV participation cap",
      "Capacity sensitivity to rebalance frequency and ADV cap",
    ],
    visual: <CapacityVisual />,
  },
  {
    id: "10",
    tag: "OPTIMAL CONSTRUCTION",
    headline: "Chart the efficient frontier across\nyour factor universe in seconds.",
    description: "The optimizer solves the quadratic program that maximizes expected return per unit of factor risk under explicit constraints. Robust optimization treats alpha uncertainty as part of construction, producing more stable allocations.",
    bullets: [
      "Efficient frontier across 50 Pareto-optimal factor portfolios",
      "Robust optimization handling alpha uncertainty",
      "Black-Litterman posterior blending history and manager views",
      "Factor Alignment Problem diagnostic above 0.7 correlation",
      "Constraint binding report with shadow prices",
      "Rebalancing cost-benefit for expected Sharpe improvement",
    ],
    visual: <FrontierVisual />,
  },
  {
    id: "12",
    tag: "SIGNAL INTELLIGENCE",
    headline: "What kind of factor are you\ntrading and will it persist?",
    description: "Factor DNA tells you why a factor performs, whether that performance should persist, and what structural category it belongs to. The auto-classifier gives a probability distribution across risk, behavioral, structural, and data-mining archetypes.",
    bullets: [
      "Octagonal radar covering IC, ICIR, half-life, crowding, purity, and independence",
      "All eight axes normalized to 0-100 for factor overlay comparisons",
      "CART classifier with probabilities across four archetypes",
      "Factor purity score after removing Fama-French five-factor variance",
      "Return anatomy split into valuation, momentum, and residual premium",
      "Correlation fingerprint across regimes",
    ],
    visual: <DnaVisual />,
  },
  {
    id: "13",
    tag: "SIGNAL HEALTH",
    headline: "Know the moment a signal\nstarts degrading before it fails",
    description: "The signal health dashboard computes IC drift, CUSUM structural break, crowding velocity, and return-characteristic alignment for every factor. A portfolio-weighted health score aggregates the results into one operational view.",
    bullets: [
      "Daily IC drift z-score for every factor",
      "CUSUM structural break detector for IC behavior change",
      "Crowding velocity as a leading forced-unwind indicator",
      "Return-characteristic alignment flags sign disagreement",
      "Portfolio-weighted health score by factor exposure",
      "Timestamped alert log with subsequent 21-day factor return",
    ],
    visual: <SignalHealthVisual />,
  },
  {
    id: "14",
    tag: "DDQ INTELLIGENCE",
    headline: "Generate your ILPA 2.0 DDQ\nfactor attribution section in minutes",
    description: "The report generator pulls live computed outputs from every other module and assembles them into a professionally typeset PDF aligned to AIMA DDQ and ILPA 2.0 section structure.",
    bullets: [
      "Auto-populated from attribution, exposure, crowding, capacity, stress, and health modules",
      "AIMA DDQ cross-reference index by question number",
      "White-label fund name, logo, contact, and disclaimer",
      "Light-mode professional PDF with serif cover and mono numeric data",
      "Versioned audit trail for data inputs and estimation parameters",
      "20-page realtime output with longer reports routed to async Research Mode",
    ],
    visual: <ReportVisual />,
  },
];

export default function FactorsV2HomePage() {
  const [previewFeature, setPreviewFeature] = useState(null);
  const [activeCluster, setActiveCluster] = useState(clusters[0].id);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("in-view");
          if (entry.target.classList.contains("q-cluster")) {
            const featureIds = String(entry.target.dataset.features || "").split(",").filter(Boolean);
            window.dispatchEvent(new CustomEvent("factors-cluster-active", { detail: { featureIds } }));
            setActiveCluster(entry.target.id);
          }
        }
      },
      { threshold: 0.18 }
    );
    document.querySelectorAll(".q-feature-card, .q-cluster").forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let startX = 0;
    const stack = document.querySelector(".qfi-stack");
    if (!stack) return undefined;
    const onStart = (event) => { startX = event.touches[0].clientX; };
    const onEnd = (event) => {
      const diff = startX - event.changedTouches[0].clientX;
      if (Math.abs(diff) < 60) return;
      const cards = [...document.querySelectorAll(".q-feature-card")];
      const current = cards.reduce((best, card) => Math.abs(card.getBoundingClientRect().top - 100) < Math.abs(best.getBoundingClientRect().top - 100) ? card : best, cards[0]);
      const index = cards.indexOf(current);
      const next = cards[Math.max(0, Math.min(cards.length - 1, index + (diff > 0 ? 1 : -1)))];
      next?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    stack.addEventListener("touchstart", onStart, { passive: true });
    stack.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      stack.removeEventListener("touchstart", onStart);
      stack.removeEventListener("touchend", onEnd);
    };
  }, []);

  useEffect(() => {
    const cards = [...document.querySelectorAll(".feature-visual")];
    if (!cards.length) return undefined;
    let raf = 0;
    const handler = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const offsets = cards.map((card) => {
          const rect = card.getBoundingClientRect();
          const progress = (window.innerHeight - rect.top) / (window.innerHeight + rect.height);
          return Math.max(-18, Math.min(18, (progress - 0.5) * 30));
        });
        cards.forEach((card, index) => {
          const offset = offsets[index];
          card.style.setProperty("--visual-parallax", `${offset}px`);
        });
      });
    };
    handler();
    window.addEventListener("scroll", handler, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", handler);
    };
  }, []);

  const featureBlocks = useMemo(() => {
    const blocks = [];
    clusters.forEach((cluster) => {
      blocks.push({ type: "cluster", ...cluster });
      features
        .filter((feature) => cluster.ids.includes(feature.id))
        .forEach((feature, localIndex) => blocks.push({ type: "feature", feature, localIndex }));
    });
    return blocks;
  }, []);

  return (
    <main className="qfi-page">
      <style jsx global>{styles}</style>
      <LiveRegimeBanner />
      <Hero />
      <StatsBar />
      <FeatureTabStrip activeCluster={activeCluster} />
      <div className="qfi-stack">
        {featureBlocks.map((block, index) =>
          block.type === "cluster" ? (
            <ClusterIntro cluster={block} key={block.id} />
          ) : (
            <FeatureSection feature={block.feature} flip={block.localIndex % 2 !== 0} key={block.feature.id} onPreview={setPreviewFeature} />
          )
        )}
      </div>
      <FooterCta />
      {previewFeature ? <FeaturePreviewOverlay featureId={previewFeature} onClose={() => setPreviewFeature(null)} /> : null}
    </main>
  );
}

function Hero() {
  return (
    <section className="q-hero" id="top">
      <FactorConstellation />
      <div className="hero-label"><i /> ATLAS · FACTOR INTELLIGENCE</div>
      <h1>
        Institutional factor
        <span>intelligence.</span>
      </h1>
      <p>14 institutional-grade factor modules. From crowding detection to allocator-ready DDQ reports.</p>
      <LiveTickerStrip />
      <div className="hero-actions">
        <a href="#valuation-exposure">Explore all features</a>
        <Link href="/labs/factors-v2/feature-12">View live demo</Link>
      </div>
      <button className="hero-chevron-button" aria-label="Scroll to feature stats" onClick={() => document.getElementById("stats-bar")?.scrollIntoView({ behavior: "smooth" })} type="button">
        <ChevronDown className="hero-chevron" size={28} />
      </button>
    </section>
  );
}

function readFeatureSummary(featureId) {
  if (typeof window === "undefined") return null;
  try {
    const summary = JSON.parse(window.localStorage.getItem(`quant360:factors-v2:${featureId}:latest-summary`) || "[]");
    return Array.isArray(summary) ? summary[0] : null;
  } catch {
    return null;
  }
}

const subscribeToStorage = (onStoreChange) => {
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
};
const getEmptyStorageSnapshot = () => null;

function useStorageValue(key) {
  const getSnapshot = useCallback(() => window.localStorage.getItem(key), [key]);
  return useSyncExternalStore(subscribeToStorage, getSnapshot, getEmptyStorageSnapshot);
}

function useFeatureSummary(featureId) {
  const raw = useStorageValue(`quant360:factors-v2:${featureId}:latest-summary`);
  return useMemo(() => {
    try {
      const summary = JSON.parse(raw || "[]");
      return Array.isArray(summary) ? summary[0] ?? null : null;
    } catch {
      return null;
    }
  }, [raw]);
}

const LIVE_TICKER_FALLBACK = [
  ["F06", "Crowding", "73rd pct", "alert"],
  ["F04", "Regime", "62% expansion", "nominal"],
  ["F13", "Signal health", "Momentum watch", "watch"],
  ["F12", "DNA", "Risk factor 58%", "nominal"],
];

function LiveTickerStrip() {
  const summary06 = useFeatureSummary("06");
  const summary04 = useFeatureSummary("04");
  const summary13 = useFeatureSummary("13");
  const summary12 = useFeatureSummary("12");
  const live = [
    ["06", summary06],
    ["04", summary04],
    ["13", summary13],
    ["12", summary12],
  ].map(([id, first]) => {
      const value = first?.value ?? first?.score ?? first?.percentile;
      if (value == null) return null;
      const numeric = Number(value);
      return [`F${id}`, first?.label || first?.name || "Latest", Number.isFinite(numeric) ? numeric.toFixed(1) : String(value), numeric >= 70 ? "alert" : numeric >= 45 ? "watch" : "nominal"];
  }).filter(Boolean);
  const items = live.length ? live : LIVE_TICKER_FALLBACK;
  return (
    <div className="hero-ticker" aria-label="Live factors briefing">
      {items.map(([id, label, value, status]) => <span className={status} key={`${id}-${label}`}><i />{id} · {label}<b>{value}</b></span>)}
    </div>
  );
}

function CountUp({ mode = "number", prefix = "", suffix = "", target }) {
  const [value, setValue] = useState(mode === "countdown" ? 999 : 0);
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();
      const start = performance.now();
      const from = mode === "countdown" ? 999 : 0;
      function tick(now) {
        const progress = Math.min((now - start) / 850, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const next = mode === "countdown" ? from - (from - target) * eased : target * eased;
        setValue(Math.round(next));
        if (progress < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    observer.observe(node);
    return () => observer.disconnect();
  }, [mode, target]);
  return <span ref={ref}>{prefix}{value.toLocaleString()}{suffix}</span>;
}

function StatsBar() {
  const stats = [
    [<CountUp key="modules" target={14} />, "Factor Modules"],
    [<CountUp key="universe" suffix="+" target={5000} />, "Universe Coverage"],
    ["10Y", "Historical Depth"],
    [<CountUp key="latency" mode="countdown" prefix="< " suffix="ms" target={150} />, "Compute Latency"],
    ["ILPA 2.0", "DDQ Standard"],
  ];
  return <section className="stats-bar" aria-label="Factor Intelligence stats" id="stats-bar">{stats.map(([value, label]) => <div className="stat" key={label}><strong>{value}</strong><span>{label}</span></div>)}</section>;
}

function FeatureTabStrip({ activeCluster }) {
  const labels = {
    "valuation-exposure": "VALUATION",
    "regime-timing": "REGIME",
    "risk-crowding": "RISK",
    "portfolio-capacity": "PORTFOLIO",
    "signal-intelligence": "INTELLIGENCE",
  };
  return (
    <nav className="feature-tab-strip" aria-label="Factors category navigation">
      {clusters.map((cluster) => <a className={activeCluster === cluster.id ? "active" : ""} href={`#${cluster.id}`} key={cluster.id}>{labels[cluster.id] || cluster.title}</a>)}
    </nav>
  );
}

function clusterStatus(featureId) {
  if (typeof window === "undefined") return "nominal";
  try {
    const summary = JSON.parse(window.localStorage.getItem(`quant360:factors-v2:${featureId}:latest-summary`) || "[]");
    const first = Array.isArray(summary) ? summary[0] : null;
    const value = Number(first?.value ?? first?.score ?? first?.percentile);
    if (Number.isFinite(value) && value >= 70) return "alert";
    if (Number.isFinite(value) && value >= 45) return "degraded";
  } catch {
    return "nominal";
  }
  return "nominal";
}

function ClusterFeaturePill({ feature }) {
  const id = feature.match(/F(\d+)/)?.[1] || "01";
  return <span className={`cluster-pill ${clusterStatus(id)}`}><i />{feature}</span>;
}

function ClusterIntro({ cluster }) {
  return (
    <section className="q-cluster" data-features={cluster.ids.join(",")} id={cluster.id}>
      <div>
        <h2>{cluster.title}</h2>
        <p>{cluster.description}</p>
      </div>
      <div className="cluster-pills">
        {cluster.features.map((feature) => <ClusterFeaturePill feature={feature} key={feature} />)}
      </div>
    </section>
  );
}

function FeatureSection({ feature, flip, onPreview }) {
  return (
    <section className={`q-feature-card ${flip ? "flip" : ""}`} id={`feature-${feature.id}`}>
      <div className="feature-copy">
        <div className="feature-tag">F{feature.id}<i />{feature.tag}<LastRunBadge featureId={feature.id} /><FeatureLiveMetric featureId={feature.id} /></div>
        <h2>{feature.headline}</h2>
        <p>{feature.description}</p>
        <ul>
          {feature.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
        </ul>
        <div className="feature-actions">
          <Link href={`/labs/factors-v2/feature-${feature.id}`}>Open Feature <ExternalLink size={15} /></Link>
          <button onClick={() => onPreview(feature.id)} type="button"><Eye size={14} /> Preview</button>
        </div>
      </div>
      <div className="feature-visual">
        <div className="watermark">F{feature.id}</div>
        {feature.visual}
      </div>
    </section>
  );
}

function FeatureLiveMetric({ featureId }) {
  const metric = useFeatureSummary(featureId);
  if (!metric) return null;
  const value = metric.value ?? metric.score ?? metric.percentile;
  const numeric = Number(value);
  const status = Number.isFinite(numeric) && numeric >= 70 ? "alert" : Number.isFinite(numeric) && numeric >= 45 ? "watch" : "nominal";
  return (
    <div className={`feature-live-metric ${status}`}>
      <span>Last run</span>
      <div><strong>{Number.isFinite(numeric) ? numeric.toFixed(numeric % 1 === 0 ? 0 : 1) : String(value)}</strong><small>{metric.label || metric.name || "Latest"}</small></div>
    </div>
  );
}

function LastRunBadge({ featureId }) {
  const getSnapshot = useCallback(() => {
    const raw = window.localStorage.getItem(`quant360:factors-v2:${featureId}:last-run`);
    if (!raw) return "Never run";
    const mins = Math.floor((Date.now() - Number(raw)) / 60000);
    return mins < 1 ? "Just now" : mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
  }, [featureId]);
  const label = useSyncExternalStore(subscribeToStorage, getSnapshot, () => "Never run");
  return <span className={`last-run-badge ${label === "Never run" ? "never" : ""}`}>{label}</span>;
}

function LiveRegimeBanner() {
  const summary06 = useFeatureSummary("06");
  const summary13 = useFeatureSummary("13");
  const summary04 = useFeatureSummary("04");
  const state = [["06", summary06], ["13", summary13], ["04", summary04]].reduce(
    (best, [id, first]) => {
      const score = Number(first?.value ?? first?.score ?? first?.percentile);
      if (Number.isFinite(score) && score > best.score) {
        return {
          label: `F${id} ${first?.label || first?.name || "latest"} ${score.toFixed(1)}`,
          status: score >= 70 ? "alert" : score >= 45 ? "watch" : "nominal",
          score,
        };
      }
      return best;
    },
    { label: "FACTOR INTELLIGENCE READY", status: "nominal", score: 0 },
  );
  return <div className={`live-regime-banner ${state.status}`}><i />{state.label}</div>;
}

function FeaturePreviewOverlay({ featureId, onClose }) {
  useEffect(() => {
    const handler = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
  return (
    <div className="feature-overlay">
      <div className="overlay-header">
        <span>Preview — F{featureId}</span>
        <button onClick={onClose} type="button" aria-label="Close preview"><X size={18} /></button>
      </div>
      <iframe src={`/labs/factors-v2/feature-${featureId}`} title={`Feature ${featureId} preview`} />
    </div>
  );
}

function GaugeDial({ value, label, sublabel }) {
  const color = value >= 70 ? TOKENS.red : value >= 50 ? TOKENS.amber : TOKENS.green;
  const angle = -90 + value * 1.8;
  const rad = (angle * Math.PI) / 180;
  const x2 = 72 + Math.cos(rad) * 48;
  const y2 = 72 + Math.sin(rad) * 48;
  return (
    <div className="mini-gauge">
      <svg className="dial-svg" viewBox="0 0 144 88" role="img" aria-label={`${label} ${value} percentile`}>
        <path d="M20 72 A52 52 0 0 1 124 72" className="dial-track" />
        <path d={`M20 72 A52 52 0 ${value > 50 ? 1 : 0} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`} className="dial-value" style={{ stroke: color }} />
        <line x1="72" y1="72" x2={x2.toFixed(2)} y2={y2.toFixed(2)} className="dial-needle" />
        <circle cx="72" cy="72" r="5" className="dial-pivot" />
        <text x="72" y="52" textAnchor="middle">{value}</text>
      </svg>
      <span>{label}</span>
      <small>{sublabel}</small>
    </div>
  );
}

function F01Visual() {
  return (
    <div className="visual-stack">
      <div className="gauge-grid">
        <GaugeDial value={23} label="Value" sublabel="+4.8% implied" />
        <GaugeDial value={81} label="Momentum" sublabel="-1.9% implied" />
        <GaugeDial value={67} label="Quality" sublabel="+0.7% implied" />
        <GaugeDial value={44} label="Low-Vol" sublabel="+1.8% implied" />
      </div>
      <ChartPanel title="Value percentile history">
        <ResponsiveContainer height={220} width="100%">
          <AreaChart data={f01History} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <defs>
              <linearGradient id="valueBand" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={TOKENS.accent} stopOpacity={0.3} />
                <stop offset="100%" stopColor={TOKENS.accent} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="year" {...axis} interval={9} />
            <YAxis {...axis} domain={[0, 100]} />
            <Tooltip contentStyle={tooltip} />
            <ReferenceLine y={30} stroke={TOKENS.green} strokeDasharray="4 4" />
            <ReferenceLine y={70} stroke={TOKENS.red} strokeDasharray="4 4" />
            <ReferenceLine x="TODAY" stroke={TOKENS.amber} strokeDasharray="4 4" />
            <Area dataKey="value" fill="url(#valueBand)" stroke={TOKENS.accent} strokeWidth={2} type="monotone" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  );
}

function ExposureBars() {
  const data = [
    ["Market Beta", 0.12],
    ["Value", 0.87],
    ["Momentum", 0.34],
    ["Quality", -0.21],
    ["Low-Vol", -0.52],
    ["Size", 0.08],
    ["Investment", 0.19],
  ].map(([factor, exposure]) => ({ factor, exposure }));
  return (
    <ChartPanel title="Active factor exposure">
      <ResponsiveContainer height={430} width="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 18, right: 28, left: 16, bottom: 12 }}>
          <CartesianGrid horizontal={false} stroke="#373E47" strokeOpacity={0.5} />
          <XAxis type="number" {...axis} domain={[-1, 1]} />
          <YAxis dataKey="factor" type="category" width={115} {...axis} />
          <Tooltip contentStyle={tooltip} />
          <ReferenceLine x={0} stroke="#F4F1EA" strokeOpacity={0.35} />
          <ReferenceLine x={0.4} stroke={TOKENS.amber} strokeDasharray="4 4" />
          <ReferenceLine x={-0.4} stroke={TOKENS.amber} strokeDasharray="4 4" />
          <Bar dataKey="exposure" radius={[0, 5, 5, 0]}>
            {data.map((row) => <Cell fill={row.exposure >= 0 ? TOKENS.green : TOKENS.red} key={row.factor} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartPanel>
  );
}

function RegimeVisual() {
  return (
    <div className="visual-stack">
      <ChartPanel title="Composite regime probability">
        <ResponsiveContainer height={330} width="100%">
          <AreaChart data={f04Regimes} margin={{ top: 10, right: 20, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="month" {...axis} interval={9} />
            <YAxis {...axis} domain={[0, 1]} />
            <Tooltip contentStyle={tooltip} />
            <Area dataKey="expansion" fill={TOKENS.green} fillOpacity={0.75} stackId="regime" stroke={TOKENS.green} type="monotone" />
            <Area dataKey="transition" fill={TOKENS.amber} fillOpacity={0.75} stackId="regime" stroke={TOKENS.amber} type="monotone" />
            <Area dataKey="stress" fill={TOKENS.red} fillOpacity={0.75} stackId="regime" stroke={TOKENS.red} type="monotone" />
            <Area dataKey="crisis" fill={TOKENS.purple} fillOpacity={0.75} stackId="regime" stroke={TOKENS.purple} type="monotone" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>
      <div className="regime-bars">
        {[["Expansion", 62, TOKENS.green], ["Transition", 28, TOKENS.amber], ["Stress", 10, TOKENS.red], ["Crisis", 0, TOKENS.purple]].map(([label, value, color]) => (
          <div className="regime-row" key={label}>
            <span>{label}</span>
            <i><b style={{ width: `${value}%`, background: color }} /></i>
            <strong>{value}%</strong>
          </div>
        ))}
      </div>
      <RegimeCalendar data={f04Regimes} />
    </div>
  );
}

function RegimeCalendar({ data }) {
  const months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
  const rows = useMemo(() => {
    const byYear = new Map();
    data.forEach((row, index) => {
      const year = 2016 + Math.floor(index / 12);
      const month = index % 12;
      const stress = Number(row.stress || 0) + Number(row.crisis || 0);
      if (!byYear.has(year)) byYear.set(year, Array(12).fill(null));
      byYear.get(year)[month] = stress;
    });
    return [...byYear.entries()].slice(-5);
  }, [data]);
  return (
    <div className="regime-calendar">
      <div className="calendar-months">{months.map((month) => <span key={month}>{month}</span>)}</div>
      {rows.map(([year, values]) => (
        <div className="calendar-row" key={year}>
          <b>{year}</b>
          {values.map((stress, index) => {
            const color = stress == null ? TOKENS.borderSoft : stress > 0.22 ? TOKENS.red : stress > 0.12 ? TOKENS.amber : TOKENS.green;
            return <i key={`${year}-${index}`} style={{ background: color, opacity: stress == null ? 0.2 : 0.35 + Math.min(stress, 0.4) }} title={`${year}-${String(index + 1).padStart(2, "0")}: stress ${(stress || 0).toFixed(2)}`} />;
          })}
        </div>
      ))}
    </div>
  );
}

function DecayVisual() {
  return (
    <ChartPanel title="Rank IC decay by horizon">
      <ResponsiveContainer height={430} width="100%">
        <LineChart data={decayData} margin={{ top: 20, right: 24, left: -12, bottom: 12 }}>
          <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="horizon" {...axis} />
          <YAxis {...axis} domain={[0, 0.08]} />
          <Tooltip contentStyle={tooltip} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} strokeDasharray="4 4" />
          <Line dataKey="value" dot={false} name="Value" stroke={TOKENS.accent} strokeWidth={2.5} type="monotone" />
          <Line dataKey="momentum" dot={false} name="Momentum" stroke={TOKENS.green} strokeWidth={2.5} type="monotone" />
          <Line dataKey="quality" dot={false} name="Quality" stroke={TOKENS.amber} strokeWidth={2.5} type="monotone" />
        </LineChart>
      </ResponsiveContainer>
    </ChartPanel>
  );
}

function CrowdingVisual() {
  return (
    <div className="visual-stack">
      <ChartPanel title="Crowding percentile">
        <div className="crowding-gauge">
          <GaugeDial value={73} label="Crowding Percentile" sublabel="above 10Y risk threshold" />
          <div className="density">
            {Array.from({ length: 38 }, (_, index) => <i key={index} style={{ height: `${10 + Math.sin(index / 4) * 9 + index * 0.8}px` }} />)}
            <b />
          </div>
        </div>
      </ChartPanel>
      <ChartPanel title="Crowding driver radar">
        <ResponsiveContainer height={240} width="100%">
          <RadarChart data={[["Valuation Stretch", 0.82], ["Autocorrelation", 0.61], ["HHI", 0.74], ["Liquidity", 0.55]].map(([axisName, value]) => ({ axis: axisName, value }))}>
            <PolarGrid stroke="#373E47" />
            <PolarAngleAxis dataKey="axis" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
            <PolarRadiusAxis axisLine={false} tick={false} domain={[0, 1]} />
            <Radar dataKey="value" fill={TOKENS.purple} fillOpacity={0.2} stroke={TOKENS.purple} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  );
}

function BacktestVisual() {
  const quintiles = [
    ["Q1", 18.4, "#2ECC71"],
    ["Q2", 12.1, "#5CD68E"],
    ["Q3", 7.8, "#9BE7BA"],
    ["Q4", 3.2, TOKENS.amber],
    ["Q5", -2.1, TOKENS.red],
  ].map(([q, ret, color]) => ({ q, ret, color }));
  return (
    <div className="visual-stack">
      <ChartPanel title="Gross / net equity curve">
        <ResponsiveContainer height={310} width="100%">
          <ComposedChart data={equityData} margin={{ top: 12, right: 18, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="month" {...axis} interval={23} />
            <YAxis {...axis} />
            <Tooltip contentStyle={tooltip} />
            <Area dataKey="gross" fill={TOKENS.green} fillOpacity={0.15} stroke={TOKENS.green} strokeWidth={2} type="monotone" />
            <Area dataKey="net" fill={TOKENS.accent} fillOpacity={0.2} stroke={TOKENS.accent} strokeWidth={2} type="monotone" />
            <Line dataKey="benchmark" dot={false} stroke={TOKENS.secondary} strokeDasharray="5 5" strokeWidth={2} type="monotone" />
          </ComposedChart>
        </ResponsiveContainer>
        <ResponsiveContainer height={120} width="100%">
          <AreaChart data={equityData} margin={{ top: 4, right: 18, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="month" {...axis} hide />
            <YAxis {...axis} domain={[-0.22, 0]} />
            <Tooltip contentStyle={tooltip} />
            <ReferenceLine y={-0.184} stroke={TOKENS.amber} strokeDasharray="4 4">
              <Label value="MAX DD -18.4%" position="insideTopRight" fill={TOKENS.amber} fontSize={11} />
            </ReferenceLine>
            <Area dataKey="drawdown" fill={TOKENS.red} fillOpacity={0.6} stroke={TOKENS.red} type="monotone" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>
      <ChartPanel title="Quintile monotonicity">
        <ResponsiveContainer height={210} width="100%">
          <BarChart data={quintiles} margin={{ top: 12, right: 18, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="q" {...axis} />
            <YAxis {...axis} />
            <Tooltip contentStyle={tooltip} />
            <ReferenceLine y={0} stroke={TOKENS.secondary} />
            <Bar dataKey="ret" radius={[6, 6, 0, 0]}>
              {quintiles.map((row) => <Cell fill={row.color} key={row.q} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  );
}

function CovarianceVisual() {
  const factors = ["MKT", "VAL", "MOM", "QLT", "LOW", "SIZE", "INV"];
  const normal = factors.map((row, i) => factors.map((col, j) => (i === j ? 1 : 0.1 + ((i + j) % 4) * 0.06)));
  const crisis = normal.map((row, i) => row.map((v, j) => (i === j ? 1 : Math.min(0.85, v + 0.32 + ((i * j) % 3) * 0.05))));
  const delta = normal.map((row, i) => row.map((v, j) => crisis[i][j] - v));
  return (
    <div className="triple-heat">
      <Heatmap title="Normal" labels={factors} matrix={normal} />
      <Heatmap title="Crisis" labels={factors} matrix={crisis} />
      <Heatmap title="Delta" labels={factors} matrix={delta} />
    </div>
  );
}

function CapacityVisual() {
  return (
    <ChartPanel title="Net alpha capacity curve">
      <ResponsiveContainer height={430} width="100%">
        <ComposedChart data={capacityData} margin={{ top: 18, right: 22, left: -10, bottom: 12 }}>
          <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="aum" {...axis} />
          <YAxis {...axis} />
          <Tooltip contentStyle={tooltip} />
          <ReferenceLine y={0} stroke={TOKENS.secondary} />
          <ReferenceLine x="1B" stroke={TOKENS.accent} strokeDasharray="4 4">
            <Label value="OPTIMAL AUM" position="top" fill={TOKENS.accent} fontSize={11} />
          </ReferenceLine>
          <ReferenceArea x1="2B" x2="10B" fill={TOKENS.red} fillOpacity={0.08} />
          <Area dataKey="alpha" fill={TOKENS.green} fillOpacity={0.2} stroke={TOKENS.green} strokeWidth={2} type="monotone" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartPanel>
  );
}

function FrontierVisual() {
  return (
    <ChartPanel title="Efficient frontier">
      <ResponsiveContainer height={430} width="100%">
        <ComposedChart data={frontierData} margin={{ top: 18, right: 24, left: -8, bottom: 12 }}>
          <CartesianGrid stroke="#373E47" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="vol" domain={[5, 19]} name="Volatility" type="number" {...axis} unit="%" />
          <YAxis dataKey="ret" name="Return" type="number" {...axis} unit="%" />
          <Tooltip contentStyle={tooltip} cursor={{ stroke: TOKENS.border }} />
          <Line dataKey="ret" dot={false} stroke={TOKENS.muted} strokeWidth={1} type="monotone" />
          <Scatter data={[{ vol: 11, ret: 10.2 }]} fill={TOKENS.accent} shape="circle" />
          <Scatter data={[{ vol: 6, ret: 4 }]} fill={TOKENS.green} shape="square" />
          <Scatter data={[{ vol: 9, ret: 9.8 }]} fill={TOKENS.amber} shape="diamond" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartPanel>
  );
}

function DnaVisual() {
  return (
    <div className="visual-stack">
      <ChartPanel title="Factor DNA radar">
        <ResponsiveContainer height={310} width="100%">
          <RadarChart data={dnaData}>
            <PolarGrid stroke="#373E47" />
            <PolarAngleAxis dataKey="axis" tick={{ fill: TOKENS.secondary, fontSize: 11 }} />
            <PolarRadiusAxis axisLine={false} tick={{ fill: TOKENS.secondary, fontSize: 10 }} domain={[0, 100]} />
            <Radar dataKey="value" fill={TOKENS.accent} fillOpacity={0.18} stroke={TOKENS.accent} strokeWidth={2} />
            <Radar dataKey="momentum" fill={TOKENS.amber} fillOpacity={0.06} stroke={TOKENS.amber} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>
      </ChartPanel>
      <ChartPanel title="Classifier output">
        <div className="classifier-home">
          <strong>RISK FACTOR</strong>
          <span>58% confidence</span>
          <div>
            <i style={{ width: "58%", background: TOKENS.green }} />
            <i style={{ width: "31%", background: TOKENS.accent }} />
            <i style={{ width: "9%", background: TOKENS.amber }} />
            <i style={{ width: "2%", background: TOKENS.red }} />
          </div>
        </div>
      </ChartPanel>
    </div>
  );
}

function SignalHealthVisual() {
  const rows = [
    ["Value", 0.042, 1.8, "ALIGNED", 100],
    ["Momentum", -0.018, -2.4, "DIVERGING", 34],
    ["Quality", 0.036, 1.4, "ALIGNED", 88],
    ["Low-Vol", 0.012, 0.4, "ALIGNED", 71],
    ["Size", 0.028, 1.1, "ALIGNED", 92],
    ["Investment", 0.009, -0.2, "ALIGNED", 61],
  ];
  return (
    <ChartPanel title="Signal health table">
      <div className="signal-table">
        <div className="signal-head">
          <span>Factor</span><span>IC 21D</span><span>Z</span><span>Alignment</span><span>Health</span>
        </div>
        {rows.map(([factor, ic, z, align, health]) => (
          <div className={`signal-row ${health < 40 ? "degraded" : ""}`} key={factor}>
            <b>{factor}</b>
            <span className={ic >= 0 ? "pos" : "neg"}>{ic.toFixed(3)}</span>
            <span className={z >= 0 ? "pos" : "neg"}>{z.toFixed(1)}</span>
            <em className={align === "ALIGNED" ? "ok" : "bad"}>{align}</em>
            <i><strong style={{ width: `${health}%`, background: health < 50 ? TOKENS.red : health < 75 ? TOKENS.amber : TOKENS.green }} /></i>
          </div>
        ))}
      </div>
    </ChartPanel>
  );
}

function ReportVisual() {
  return (
    <div className="report-preview">
      <div className="report-paper">
        <h3>QUANT360 CAPITAL</h3>
        <p>Factor Attribution & Risk Report — Q1 2026</p>
        <section>
          <strong>FACTOR ATTRIBUTION</strong>
          <div className="paper-rule" />
          <div className="paper-bars">
            {["MKT", "VAL", "MOM", "QLT", "SEL", "INT"].map((label, index) => {
              const value = [42, 18, 9, -4, 11, -3][index];
              return <i key={label} style={{ height: `${Math.abs(value) * 2.5}px`, background: value >= 0 ? "#2B8A3E" : "#C0392B" }}><span>{label}</span></i>;
            })}
          </div>
        </section>
      </div>
      <Link href="/labs/factors-v2/feature-14"><Download size={16} /> Download PDF</Link>
    </div>
  );
}

function WaterfallVisual({ data }) {
  const rows = data.map(([name, value], index) => {
    const previous = index ? data.slice(0, index).reduce((sum, item) => sum + item[1], 0) : 0;
    return { name, value, start: previous, end: previous + value };
  });
  const min = Math.min(-15, ...rows.map((row) => Math.min(row.start, row.end)));
  const max = Math.max(10, ...rows.map((row) => Math.max(row.start, row.end)));
  const y = (value) => 330 - ((value - min) / (max - min)) * 250;
  const step = 820 / rows.length;
  return (
    <ChartPanel title="Attribution waterfall">
      <svg className="home-waterfall" viewBox="0 0 900 390" role="img" aria-label="Waterfall attribution">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => <line className="wf-grid" key={tick} x1="42" x2="875" y1={70 + tick * 250} y2={70 + tick * 250} />)}
        <line className="wf-zero" x1="42" x2="875" y1={y(0)} y2={y(0)} />
        {rows.map((row, index) => {
          const x = 56 + index * step;
          const y1 = y(row.start);
          const y2 = y(row.end);
          const top = Math.min(y1, y2);
          const height = Math.max(3, Math.abs(y2 - y1));
          return (
            <g key={row.name}>
              <rect className={row.value >= 0 ? "wf-pos" : "wf-neg"} height={height} rx="5" width="54" x={x} y={top} />
              {index < rows.length - 1 ? <line className="wf-link" x1={x + 54} x2={56 + (index + 1) * step} y1={y2} y2={y2} /> : null}
              <text className="wf-text" textAnchor="middle" x={x + 27} y={top - 8}>{row.value > 0 ? "+" : ""}{row.value.toFixed(1)}%</text>
              <text className="wf-label" textAnchor="middle" x={x + 27} y="360">{row.name}</text>
            </g>
          );
        })}
      </svg>
    </ChartPanel>
  );
}

function Heatmap({ labels, matrix, title }) {
  return (
    <div className="hm">
      <strong>{title}</strong>
      <div className="hm-grid" style={{ gridTemplateColumns: `48px repeat(${labels.length}, 1fr)` }}>
        <span />
        {labels.map((label) => <span key={label}>{label}</span>)}
        {matrix.flatMap((row, rowIndex) => [
          <b key={`${labels[rowIndex]}-label`}>{labels[rowIndex]}</b>,
          ...row.map((value, colIndex) => {
            const opacity = Math.min(0.9, Math.abs(value));
            return <i key={`${rowIndex}-${colIndex}`} style={{ background: value >= 0 ? `rgba(248,81,73,${0.12 + opacity * 0.65})` : `rgba(245,164,0,${0.12 + opacity * 0.65})` }}>{Math.abs(value) >= 0.3 || rowIndex === colIndex ? value.toFixed(2) : ""}</i>;
          }),
        ])}
      </div>
    </div>
  );
}

function ChartPanel({ children, title }) {
  return (
    <div className="chart-panel">
      <span>{title}</span>
      {children}
    </div>
  );
}

function FactorConstellation() {
  const svgRef = useRef(null);
  const graph = useMemo(() => {
    const nodes = features.map((feature, index) => {
      const summary = typeof window !== "undefined" ? readFeatureSummary(feature.id) : null;
      const score = Number(summary?.value ?? summary?.score ?? summary?.percentile);
      const ic = Number.isFinite(score) ? Math.max(0.02, Math.min(0.12, score / 900)) : 0.035 + (index % 5) * 0.008;
      const crowding = Number.isFinite(score) ? score : [23, 46, 58, 62, 41, 73, 38, 69, 54, 32, 67, 58, 34, 25][index] || 45;
      return {
        id: feature.id,
        label: `F${feature.id}`,
        name: feature.shortName || feature.tag || feature.headline.split("\n")[0],
        r: 7 + ic * 115,
        crowding,
      };
    });
    const links = [];
    nodes.forEach((source, i) => {
      nodes.slice(i + 1).forEach((target, j) => {
        const distance = Math.abs(Number(source.id) - Number(target.id));
        const sameCluster = Math.floor((Number(source.id) - 1) / 3) === Math.floor((Number(target.id) - 1) / 3);
        const corr = sameCluster ? 0.35 + ((i + j) % 3) * 0.08 : distance <= 2 ? 0.18 : distance === 6 ? -0.22 : 0;
        if (Math.abs(corr) > 0.15) links.push({ source: source.id, target: target.id, value: corr });
      });
    });
    return { nodes, links };
  }, []);

  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return undefined;
    const width = 420;
    const height = 380;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();

    const defs = svg.append("defs");
    const glow = defs.append("radialGradient").attr("id", "constellationGlow");
    glow.append("stop").attr("offset", "0%").attr("stop-color", TOKENS.accent).attr("stop-opacity", 0.42);
    glow.append("stop").attr("offset", "100%").attr("stop-color", TOKENS.accent).attr("stop-opacity", 0);
    svg.append("circle").attr("cx", width / 2).attr("cy", height / 2).attr("r", 170).attr("fill", "url(#constellationGlow)");

    const color = (score) => score >= 70 ? TOKENS.red : score >= 45 ? TOKENS.amber : TOKENS.green;
    const links = graph.links.map((link) => ({ ...link }));
    const nodes = graph.nodes.map((node) => ({ ...node }));
    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id((d) => d.id).distance((d) => 72 + (1 - Math.abs(d.value)) * 84).strength(0.58))
      .force("charge", d3.forceManyBody().strength(-185))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide((d) => d.r + 18));

    const link = svg.append("g")
      .attr("class", "constellation-links")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => d.value >= 0 ? "rgba(245,164,0,.34)" : "rgba(248,81,73,.34)")
      .attr("stroke-width", (d) => Math.max(0.8, Math.abs(d.value) * 4.2))
      .attr("stroke-dasharray", (d) => d.value < 0 ? "4 4" : null);

    const node = svg.append("g")
      .attr("class", "constellation-nodes")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => d.r)
      .attr("fill", (d) => color(d.crowding))
      .attr("fill-opacity", 0.18)
      .attr("stroke", (d) => color(d.crowding))
      .attr("stroke-width", 2)
      .attr("data-feature", (d) => d.id)
      .on("click", (_, d) => {
        document.getElementById(`feature-${d.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .call(d3.drag()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    const label = svg.append("g")
      .attr("class", "constellation-labels")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => d.label)
      .attr("text-anchor", "middle")
      .attr("fill", TOKENS.secondary)
      .attr("font-size", 10)
      .attr("font-weight", 800)
      .attr("font-family", "Quant360 Mono, JetBrains Mono, monospace");

    simulation.on("tick", () => {
      nodes.forEach((d) => {
        d.x = Math.max(36, Math.min(width - 36, d.x));
        d.y = Math.max(32, Math.min(height - 32, d.y));
      });
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y + d.r + 14);
    });

    return () => simulation.stop();
  }, [graph]);
  return (
    <svg ref={svgRef} className="factor-constellation" viewBox="0 0 420 380" aria-label="Interactive factor correlation constellation" role="img" />
  );
}

function FooterCta() {
  return (
    <section className="footer-cta">
      <h2>Ready to run your first analysis?</h2>
      <p>Start with Factor DNA to understand your signal, or Crowding Monitor if you are managing an active quant book today.</p>
      <div>
        <Link href="/labs/factors-v2/feature-12">Start with F12 DNA</Link>
        <Link href="/labs/factors-v2/feature-06">Start with F06 Crowding</Link>
      </div>
    </section>
  );
}

const styles = `
  @font-face { font-family: "Quant360 Inter"; src: url("/fonts/inter-5.woff2") format("woff2"); font-weight: 400 800; font-style: normal; font-display: swap; }
  @font-face { font-family: "Quant360 Mono"; src: url("/fonts/jetbrains-5.woff2") format("woff2"); font-weight: 400 800; font-style: normal; font-display: swap; }
  body { background: #050505; }
  .qfi-page { min-height: 100dvh; background: #050505; color: #F4F1EA; font-family: "Quant360 Inter", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; overflow-x: hidden; }
  .live-regime-banner { position: fixed; left: 50%; top: 12px; transform: translateX(-50%); z-index: 40; height: 30px; padding: 0 13px; border: 1px solid #2E2618; border-radius: 999px; background: rgba(13,17,23,.86); backdrop-filter: blur(14px); color: #A8A29A; display: inline-flex; align-items: center; gap: 8px; font: 800 10px "Quant360 Mono", "JetBrains Mono", monospace; letter-spacing: .12em; pointer-events: none; }
  .live-regime-banner i { width: 7px; height: 7px; border-radius: 999px; background: #3FB950; box-shadow: 0 0 10px rgba(63,185,80,.45); }
  .live-regime-banner.watch i { background: #F5A400; box-shadow: 0 0 10px rgba(210,153,34,.45); }
  .live-regime-banner.alert i { background: #F85149; box-shadow: 0 0 10px rgba(248,81,73,.48); }
  .q-hero { min-height: 100vh; position: relative; display: grid; place-items: center; align-content: center; text-align: center; padding: 96px 24px 72px; background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(245,164,0,0.08) 0%, transparent 60%), #050505; isolation: isolate; overflow: hidden; }
  .q-hero::before { content: ""; position: absolute; inset: 0; background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(245,164,0,0.1), transparent 60%); z-index: -1; pointer-events: none; }
  .factor-constellation { position: absolute; right: clamp(24px, 4vw, 72px); top: 24%; width: min(360px, 24vw); height: 330px; opacity: .28; z-index: 0; overflow: visible; transform: translateX(0); }
  .factor-constellation .constellation-nodes circle { filter: drop-shadow(0 0 10px rgba(245,164,0,.26)); cursor: grab; transition: fill-opacity 150ms ease, stroke-width 150ms ease; }
  .factor-constellation .constellation-nodes circle:hover { fill-opacity: .36; stroke-width: 3; cursor: grab; }
  .factor-constellation .constellation-nodes circle:active { cursor: grabbing; }
  .factor-constellation .constellation-labels text { letter-spacing: .08em; pointer-events: none; }
  .q-hero > *:not(.factor-constellation) { position: relative; z-index: 1; }
  .hero-label { color: #F5A400; font-size: 11px; font-weight: 600; letter-spacing: .22em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 10px; margin-bottom: 24px; }
  .hero-label i { width: 1px; height: 12px; background: #F5A400; display: block; }
  .q-hero h1 { margin: 0; font-size: 72px; line-height: .96; font-family: Georgia, "Times New Roman", serif; font-weight: 700; letter-spacing: -0.04em; }
  .q-hero h1 span { display: block; color: #F5A400; }
  .q-hero p { margin: 24px auto 0; max-width: 600px; color: #A8A29A; font-size: 20px; line-height: 1.55; }
  .hero-ticker { margin: 22px auto 0; max-width: min(860px, 92vw); display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
  .hero-ticker span { min-height: 30px; display: inline-flex; align-items: center; gap: 8px; border: 1px solid #2E2618; border-radius: 999px; background: rgba(13,17,23,.72); color: #A8A29A; padding: 0 11px; font: 800 10px "Quant360 Mono", "JetBrains Mono", monospace; letter-spacing: .08em; }
  .hero-ticker i { width: 6px; height: 6px; border-radius: 999px; background: #3FB950; box-shadow: 0 0 10px rgba(63,185,80,.45); }
  .hero-ticker b { color: #F4F1EA; font-weight: 800; }
  .hero-ticker .watch i { background: #F5A400; box-shadow: 0 0 10px rgba(210,153,34,.45); }
  .hero-ticker .alert i { background: #F85149; box-shadow: 0 0 10px rgba(248,81,73,.45); }
  .hero-actions { margin-top: 34px; display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
  .hero-actions a, .footer-cta a { height: 48px; border-radius: 8px; padding: 0 20px; display: inline-flex; align-items: center; justify-content: center; text-decoration: none; font-weight: 700; font-size: 14px; transition: transform 150ms ease, border-color 150ms ease, color 150ms ease, background 150ms ease; }
  .hero-actions a:first-child, .footer-cta a:first-child { background: #F5A400; color: white; border: 1px solid #F5A400; }
  .hero-actions a:last-child, .footer-cta a:last-child { background: transparent; color: #A8A29A; border: 1px solid #2E2618; }
  .hero-actions a:hover, .footer-cta a:hover { transform: translateY(-1px); }
  .hero-chevron-button { position: absolute; bottom: 28px; border: 0; background: transparent; color: #6F675C; cursor: pointer; width: 44px; height: 44px; display: grid; place-items: center; }
  .hero-chevron { color: #6F675C; animation: pulseChevron 2s ease-in-out infinite; }
  @keyframes pulseChevron { 0%, 100% { opacity: .4; transform: translateY(0); } 50% { opacity: .8; transform: translateY(6px); } }
  .stats-bar { height: 80px; background: #0B0B0B; border-top: 1px solid #1C1710; border-bottom: 1px solid #1C1710; display: grid; grid-template-columns: repeat(5, 1fr); }
  .stat { display: grid; place-items: center; align-content: center; gap: 5px; border-left: 1px solid #1C1710; }
  .stat:first-child { border-left: 0; }
  .stat strong { font-family: "Quant360 Mono", "JetBrains Mono", "IBM Plex Mono", Consolas, monospace; font-size: 28px; color: #F4F1EA; line-height: 1; }
  .stat span { color: #A8A29A; font-size: 11px; text-transform: uppercase; letter-spacing: .16em; }
  .feature-tab-strip { position: sticky; top: 0; z-index: 10; height: 48px; background: rgba(13,17,23,.94); backdrop-filter: blur(16px); border-bottom: 1px solid #1C1710; display: flex; align-items: center; gap: 0; padding: 0 clamp(16px, 3vw, 44px); overflow-x: auto; scrollbar-width: none; }
  .feature-tab-strip::-webkit-scrollbar { display: none; }
  .feature-tab-strip a { height: 100%; display: inline-flex; align-items: center; padding: 0 18px; color: #A8A29A; font-size: 13px; font-weight: 800; text-decoration: none; letter-spacing: .08em; border-bottom: 2px solid transparent; white-space: nowrap; transition: color 150ms ease, border-color 150ms ease, background 150ms ease; }
  .feature-tab-strip a:hover { color: #F4F1EA; background: rgba(255,255,255,.02); }
  .feature-tab-strip a.active { color: #F4F1EA; border-bottom-color: #F5A400; }
  .qfi-stack { display: grid; gap: 2px; padding: 0 clamp(16px, 3vw, 44px); }
  .q-cluster { min-height: 270px; padding: 64px clamp(18px, 4vw, 64px); border-top: 1px solid #1C1710; display: grid; grid-template-columns: minmax(0, 1fr) minmax(340px, 520px); gap: 38px; align-items: center; opacity: 0; transform: translateY(24px); transition: opacity 400ms ease-out, transform 400ms ease-out; }
  .q-cluster.in-view { opacity: 1; transform: translateY(0); }
  .q-cluster h2 { margin: 0 0 14px; font-size: 40px; line-height: 1.05; letter-spacing: -0.02em; }
  .q-cluster p { margin: 0; max-width: 500px; color: #A8A29A; font-size: 16px; line-height: 1.7; }
  .cluster-pills { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
  .cluster-pills span { background: #15120B; border: 1px solid #2E2618; color: #F4F1EA; border-radius: 999px; padding: 10px 13px; font-size: 12px; font-weight: 700; display: inline-flex; align-items: center; gap: 8px; }
  .cluster-pills i { width: 7px; height: 7px; border-radius: 999px; background: #3FB950; box-shadow: 0 0 10px rgba(63,185,80,.35); }
  .cluster-pill.degraded i { background: #F5A400; box-shadow: 0 0 10px rgba(210,153,34,.35); }
  .cluster-pill.alert i { background: #F85149; box-shadow: 0 0 10px rgba(248,81,73,.45); }
  .q-feature-card { position: relative; min-height: 600px; display: grid; grid-template-columns: 45% 55%; gap: 32px; align-items: center; background: #0B0B0B; border: 1px solid #1C1710; border-radius: 16px; padding: 64px; overflow: hidden; opacity: 0; transform: translateY(24px); transition: opacity 400ms ease-out, transform 400ms ease-out; }
  .q-feature-card::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 1px; background: linear-gradient(90deg, transparent, rgba(245,164,0,0.5), transparent); }
  .q-feature-card.in-view { opacity: 1; transform: translateY(0); }
  .q-feature-card.in-view .feature-visual { transition-delay: 120ms; opacity: 1; transform: translateY(0); }
  .q-feature-card.flip .feature-copy { order: 2; }
  .q-feature-card.flip .feature-visual { order: 1; }
  .feature-copy { min-width: 0; }
  .feature-tag { color: #F5A400; font-size: 11px; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; display: flex; align-items: center; gap: 12px; margin-bottom: 22px; flex-wrap: wrap; }
  .feature-tag i { width: 16px; height: 1px; background: #F5A400; display: block; }
  .last-run-badge { color: #A8A29A; border: 1px solid #2E2618; background: #15120B; border-radius: 999px; padding: 5px 8px; font: 800 9px "Quant360 Mono", "JetBrains Mono", monospace; letter-spacing: .08em; }
  .last-run-badge.never { color: #6F675C; }
  .feature-live-metric { margin-left: auto; display: flex; flex-direction: column; align-items: flex-end; gap: 2px; min-width: 92px; }
  .feature-live-metric > span { color: #6F675C !important; font-size: 8px !important; letter-spacing: .16em; }
  .feature-live-metric div { display: flex; align-items: baseline; gap: 5px; }
  .feature-live-metric strong { font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 22px; font-weight: 800; line-height: 1; letter-spacing: -0.02em; }
  .feature-live-metric small { color: #A8A29A; font-size: 9px !important; text-transform: uppercase; letter-spacing: .1em; opacity: .72; max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .feature-live-metric.nominal strong { color: #3FB950; }
  .feature-live-metric.watch strong { color: #F5A400; }
  .feature-live-metric.alert strong { color: #F85149; }
  .feature-copy h2 { white-space: pre-line; margin: 0; max-width: 560px; color: #F4F1EA; font-size: 48px; line-height: 1.05; letter-spacing: -0.02em; }
  .feature-copy p { max-width: 480px; margin: 24px 0 0; color: #A8A29A; font-size: 16px; line-height: 1.75; }
  .feature-copy ul { margin: 24px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
  .feature-copy li { color: #F4F1EA; font-size: 14px; line-height: 1.65; display: grid; grid-template-columns: 14px 1fr; gap: 10px; max-width: 540px; }
  .feature-copy li::before { content: ""; width: 4px; height: 4px; margin-top: 10px; background: #F5A400; display: block; }
  .feature-actions { display: flex; align-items: center; gap: 10px; margin-top: 30px; flex-wrap: wrap; }
  .feature-actions a, .feature-actions button { height: 44px; border-radius: 8px; padding: 0 20px; display: inline-flex; align-items: center; gap: 10px; color: #F4F1EA; text-decoration: none; background: #15120B; border: 1px solid #2E2618; font-size: 13px; font-weight: 700; transition: color 150ms ease, border-color 150ms ease, transform 150ms ease; cursor: pointer; }
  .feature-actions button { padding: 0 14px; color: #A8A29A; }
  .feature-actions a:hover, .feature-actions button:hover { color: #F5A400; border-color: #F5A400; transform: translateY(-1px); }
  .feature-visual { position: relative; min-height: 480px; background: #050505; border: 1px solid #2E2618; border-radius: 12px; padding: 24px; box-shadow: 0 0 60px rgba(245,164,0,0.06); opacity: 0; transform: translateY(24px); transition: opacity 400ms ease-out 120ms, transform 400ms ease-out 120ms; cursor: crosshair; overflow: hidden; }
  .q-feature-card.in-view .feature-visual { transform: translateY(var(--visual-parallax, 0px)); }
  .watermark { position: absolute; right: 18px; bottom: 4px; color: #F4F1EA; font-size: 72px; font-weight: 800; opacity: .05; pointer-events: none; }
  .visual-stack { display: grid; gap: 8px; height: 100%; }
  .chart-panel { position: relative; background: #0B0B0B; border: 1px solid #1C1710; border-radius: 10px; padding: 18px; min-height: 0; }
  .chart-panel > span { display: block; margin-bottom: 12px; color: #A8A29A; font-size: 11px; text-transform: uppercase; letter-spacing: .14em; font-weight: 700; }
  .gauge-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .mini-gauge { display: grid; place-items: center; background: #0B0B0B; border: 1px solid #1C1710; border-radius: 10px; padding: 18px 10px; }
  .dial-svg { width: 144px; height: 88px; overflow: visible; }
  .dial-track, .dial-value { fill: none; stroke-width: 12; stroke-linecap: round; }
  .dial-track { stroke: #1C1710; }
  .dial-needle { stroke: #F4F1EA; stroke-width: 2.5; stroke-linecap: round; }
  .dial-pivot { fill: #F5A400; stroke: #0B0B0B; stroke-width: 2; }
  .dial-svg text { fill: #F4F1EA; font: 800 28px "Quant360 Mono", "JetBrains Mono", monospace; }
  .mini-gauge span { margin-top: 10px; color: #F4F1EA; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em; }
  .mini-gauge small { margin-top: 4px; color: #A8A29A; font-size: 11px; }
  .regime-bars { display: grid; gap: 10px; background: #0B0B0B; border: 1px solid #1C1710; border-radius: 10px; padding: 18px; }
  .regime-row { display: grid; grid-template-columns: 110px 1fr 58px; gap: 12px; align-items: center; color: #A8A29A; font-size: 12px; }
  .regime-row i { height: 10px; background: #1C1710; border-radius: 999px; overflow: hidden; }
  .regime-row b { display: block; height: 100%; border-radius: 999px; }
  .regime-row strong { color: #F4F1EA; font-family: "Quant360 Mono", "JetBrains Mono", monospace; text-align: right; }
  .regime-calendar { background: #0B0B0B; border: 1px solid #1C1710; border-radius: 10px; padding: 12px; display: grid; gap: 7px; }
  .calendar-months, .calendar-row { display: grid; grid-template-columns: 44px repeat(12, minmax(10px, 1fr)); gap: 5px; align-items: center; }
  .calendar-months { padding-left: 44px; grid-template-columns: repeat(12, minmax(10px, 1fr)); }
  .calendar-months span { color: #6F675C; font: 800 9px "Quant360 Mono", "JetBrains Mono", monospace; text-align: center; }
  .calendar-row b { color: #A8A29A; font: 800 10px "Quant360 Mono", "JetBrains Mono", monospace; }
  .calendar-row i { height: 14px; border-radius: 3px; border: 1px solid rgba(255,255,255,.05); cursor: crosshair; }
  .crowding-gauge { display: grid; place-items: center; gap: 14px; }
  .density { position: relative; height: 54px; display: flex; align-items: end; gap: 4px; }
  .density i { width: 7px; background: #2E2618; border-radius: 2px 2px 0 0; }
  .density b { position: absolute; left: 73%; bottom: 0; width: 2px; height: 58px; background: #F5A400; box-shadow: 0 0 12px rgba(245,164,0,.55); }
  .triple-heat { display: grid; grid-template-columns: repeat(3, minmax(280px, 1fr)); gap: 8px; height: 100%; overflow-x: auto; padding-bottom: 4px; }
  .hm { background: #0B0B0B; border: 1px solid #1C1710; border-radius: 10px; padding: 12px; overflow-x: auto; min-width: 0; }
  .hm strong { display: block; color: #A8A29A; font-size: 11px; text-transform: uppercase; letter-spacing: .12em; margin-bottom: 10px; }
  .hm-grid { display: grid; min-width: 280px; gap: 2px; }
  .hm-grid span, .hm-grid b, .hm-grid i { height: 30px; display: grid; place-items: center; color: #A8A29A; font: 700 10px "Quant360 Mono", "JetBrains Mono", monospace; }
  .hm-grid b { color: #F4F1EA; justify-content: start; }
  .hm-grid i { color: #F4F1EA; background: #15120B; }
  .home-waterfall { width: 100%; min-width: 720px; height: 390px; }
  .wf-grid { stroke: #373E47; stroke-opacity: .5; }
  .wf-zero { stroke: #A8A29A; stroke-dasharray: 4 4; opacity: .7; }
  .wf-pos { fill: #3FB950; }
  .wf-neg { fill: #F85149; }
  .wf-link { stroke: #A8A29A; stroke-dasharray: 3 4; opacity: .62; }
  .wf-text, .wf-label { fill: #F4F1EA; font: 700 11px "Quant360 Mono", "JetBrains Mono", monospace; }
  .wf-label { fill: #A8A29A; font-size: 10px; }
  .classifier-home strong { display: block; font-size: 20px; color: #F4F1EA; margin-bottom: 4px; }
  .classifier-home span { color: #A8A29A; font-family: "Quant360 Mono", "JetBrains Mono", monospace; font-size: 12px; }
  .classifier-home div { margin-top: 18px; display: flex; height: 30px; border-radius: 999px; overflow: hidden; background: #1C1710; }
  .classifier-home i { display: block; height: 100%; }
  .signal-table { border: 1px solid #1C1710; border-radius: 10px; overflow-x: auto; }
  .signal-head, .signal-row { display: grid; grid-template-columns: 1.2fr .8fr .7fr 1.1fr 1.1fr; align-items: center; gap: 10px; min-width: 0; }
  .signal-head { height: 44px; background: #15120B; color: #A8A29A; padding: 0 14px; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
  .signal-row { height: 54px; padding: 0 14px; border-top: 1px solid #1C1710; font: 600 12px "Quant360 Mono", "JetBrains Mono", monospace; position: relative; }
  .signal-row.degraded { animation: pulseRow 2s ease-in-out infinite; }
  @keyframes pulseRow { 0%,100% { background: rgba(248,81,73,.04); } 50% { background: rgba(248,81,73,.14); } }
  .signal-row .pos { color: #3FB950; } .signal-row .neg { color: #F85149; }
  .signal-row em { justify-self: start; border-radius: 999px; padding: 5px 8px; font-style: normal; font-family: Inter, sans-serif; font-size: 10px; font-weight: 800; }
  .signal-row em.ok { color: #3FB950; background: rgba(63,185,80,.1); } .signal-row em.bad { color: #F85149; background: rgba(248,81,73,.1); }
  .signal-row i { height: 8px; border-radius: 999px; background: #1C1710; overflow: hidden; }
  .signal-row i strong { display: block; height: 100%; border-radius: 999px; }
  .report-preview { display: grid; place-items: center; gap: 18px; }
  .report-paper { width: min(390px, 100%); min-height: 500px; background: #FFFFFF; color: #111318; padding: 44px 34px; box-shadow: 0 20px 70px rgba(0,0,0,.42); }
  .report-paper h3 { margin: 0; text-align: center; font: 500 32px Georgia, serif; letter-spacing: .04em; }
  .report-paper p { text-align: center; color: #4A5168; font-size: 14px; margin: 12px 0 46px; }
  .report-paper strong { color: #111318; font-size: 12px; letter-spacing: .16em; }
  .paper-rule { height: 1px; background: #D0D7DE; margin: 10px 0 28px; }
  .paper-bars { height: 150px; display: flex; align-items: end; gap: 12px; justify-content: center; }
  .paper-bars i { width: 28px; display: block; position: relative; }
  .paper-bars i span { position: absolute; bottom: -18px; left: 50%; transform: translateX(-50%); color: #4A5168; font: 700 8px "Quant360 Mono", "JetBrains Mono", monospace; }
  .report-preview a { height: 42px; border-radius: 8px; padding: 0 16px; display: inline-flex; align-items: center; gap: 8px; text-decoration: none; background: #F5A400; color: white; font-weight: 800; font-size: 13px; }
  .feature-overlay { position: fixed; inset: 18px; z-index: 70; background: #050505; border: 1px solid #2E2618; border-radius: 14px; box-shadow: 0 30px 90px rgba(0,0,0,.72); overflow: hidden; display: grid; grid-template-rows: 52px minmax(0, 1fr); }
  .overlay-header { background: #0B0B0B; border-bottom: 1px solid #2E2618; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; color: #F4F1EA; font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
  .overlay-header button { width: 34px; height: 34px; border-radius: 8px; border: 1px solid #2E2618; background: #15120B; color: #F4F1EA; display: grid; place-items: center; cursor: pointer; }
  .feature-overlay iframe { width: 100%; height: 100%; border: 0; background: #050505; }
  .footer-cta { padding: 120px 24px; text-align: center; background: #050505; }
  .footer-cta h2 { margin: 0; font-size: 48px; color: #F4F1EA; letter-spacing: -0.02em; }
  .footer-cta p { max-width: 560px; margin: 18px auto 30px; color: #A8A29A; font-size: 18px; line-height: 1.65; }
  .footer-cta div { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
  @media (max-width: 1120px) {
    .q-feature-card, .q-feature-card.flip { grid-template-columns: 1fr; padding: 42px 28px; }
    .q-feature-card.flip .feature-copy, .q-feature-card.flip .feature-visual { order: initial; }
    .feature-visual { min-height: 420px; }
    .q-cluster { grid-template-columns: 1fr; }
    .cluster-pills { justify-content: flex-start; }
    .factor-constellation { display: none; }
  }
  @media (max-width: 1380px) {
    .factor-constellation { opacity: .12; right: -80px; width: 300px; }
  }
  @media (max-width: 760px) {
    .q-hero h1 { font-size: 44px; }
    .q-hero p { font-size: 17px; }
    .stats-bar { height: auto; grid-template-columns: 1fr; }
    .stat { min-height: 72px; border-left: 0; border-top: 1px solid #1C1710; }
    .feature-copy h2, .footer-cta h2 { font-size: 34px; }
    .q-cluster h2 { font-size: 32px; }
    .q-feature-card { padding: 30px 18px; border-radius: 12px; }
    .feature-visual { padding: 14px; overflow-x: auto; }
    .gauge-grid, .triple-heat { grid-template-columns: 1fr; }
    .factor-constellation { display: none; }
  }
`;
