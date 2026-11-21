import { BrainCircuit, CandlestickChart, FlaskConical, ListFilter, type LucideIcon } from "lucide-react";

export type ModuleLink = { id: string; label: string; href: string; icon: LucideIcon; pages?: { label: string; href: string }[] };

/** Workspace modules and their pages; drives the top-bar menus on every page. */
export const MODULES: ModuleLink[] = [
  { id: "screener", label: "Screener", href: "/screener", icon: ListFilter, pages: [
    { label: "Screen", href: "/screener/screen" }, { label: "Rank", href: "/screener/composite" }, { label: "Test", href: "/screener/backtest" },
    { label: "Monitor", href: "/screener/alerts" }, { label: "Saved", href: "/screener/saved" }, { label: "More", href: "/screener/more" }] },
  { id: "studio", label: "Studio", href: "/studio", icon: CandlestickChart, pages: [
    { label: "Build", href: "/studio/build" }, { label: "Backtest", href: "/studio/backtest" }, { label: "Optimise", href: "/studio/optimise" },
    { label: "Validate", href: "/studio/validate" }, { label: "Portfolio", href: "/studio/portfolio" }, { label: "Live", href: "/studio/live" }, { label: "Chart", href: "/studio/chart" }] },
  { id: "ml", label: "ML", href: "/ml", icon: BrainCircuit, pages: [
    { label: "Validate", href: "/ml/validate" }, { label: "Alpha", href: "/ml/alpha" }, { label: "Volatility & risk", href: "/ml/volatility" },
    { label: "Allocation", href: "/ml/allocation" }, { label: "Strategy studio", href: "/ml/studio" }] },
  { id: "research", label: "Research", href: "/research", icon: FlaskConical, pages: [
    { label: "Signal", href: "/research/signal" }, { label: "Report card", href: "/research/report" }, { label: "Pricing tests", href: "/research/canonical" },
    { label: "Robustness", href: "/research/robustness" }, { label: "Causal", href: "/research/causal" }, { label: "Decay & novelty", href: "/research/decay" }] },
];
