import { BrainCircuit, CandlestickChart, FlaskConical, ListFilter, type LucideIcon } from "lucide-react";

export type ModuleLink = { id: string; label: string; href: string; icon: LucideIcon; blurb: string; pages?: { label: string; href: string }[] };

/** Workspace modules and their pages; drives the top-bar menus on every page. */
export const MODULES: ModuleLink[] = [
  { id: "screener", blurb: "Find and rank names", label: "Screener", href: "/screener", icon: ListFilter, pages: [
    { label: "Overview", href: "/screener" },
    { label: "Screen", href: "/screener/screen" }, { label: "Rank", href: "/screener/composite" }, { label: "Test", href: "/screener/backtest" },
    { label: "Monitor", href: "/screener/alerts" }, { label: "Saved", href: "/screener/saved" }, { label: "More", href: "/screener/more" }] },
  { id: "studio", blurb: "Write, test and run strategies", label: "Studio", href: "/studio", icon: CandlestickChart, pages: [
    { label: "Home", href: "/studio" },
    { label: "Build", href: "/studio/build" }, { label: "Backtest", href: "/studio/backtest" }, { label: "Optimise", href: "/studio/optimise" },
    { label: "Validate", href: "/studio/validate" }, { label: "Portfolio", href: "/studio/portfolio" }, { label: "Live", href: "/studio/live" }, { label: "Data", href: "/studio/data" }, { label: "Report", href: "/studio/report" }] },
  { id: "ml", blurb: "Models, risk and allocation", label: "ML", href: "/ml", icon: BrainCircuit, pages: [
    { label: "Overview", href: "/ml" },
    { label: "Validate", href: "/ml/validate" }, { label: "Alpha", href: "/ml/alpha" }, { label: "Volatility & risk", href: "/ml/volatility" },
    { label: "Allocation", href: "/ml/allocation" }, { label: "Strategy studio", href: "/ml/studio" }] },
  { id: "research", blurb: "Test a signal like a referee", label: "Research", href: "/research", icon: FlaskConical, pages: [
    { label: "Overview", href: "/research" },
    { label: "Signal", href: "/research/signal" }, { label: "Report card", href: "/research/report" }, { label: "Pricing tests", href: "/research/canonical" },
    { label: "Robustness", href: "/research/robustness" }, { label: "Causal", href: "/research/causal" }, { label: "Decay & novelty", href: "/research/decay" }] },
];
