"use client";

import { motion } from "framer-motion";
import { openQuickLook } from "@/kit/QuickLook";
import type { Tone } from "./layouts";

/** One run's lead figure over a full-width picture: lines (equity), bars (ranked names) or a stack (share by group). */
export type HeroSpec = {
  figure: string;
  tone?: Tone | null;
  versus?: string;
  line?: string;
  lines?: { label: string; values: number[]; color: string }[];
  bars?: { label: string; value: number }[];
  stack?: { label: string; value: number }[];
};

const TONE: Record<string, string> = { up: "var(--up)", down: "var(--down)", warn: "var(--warn)" };
const STACK = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--c7)", "var(--c8)"];
const ease = [0.2, 0, 0, 1] as const;

export function HeroResult({ spec }: { spec: HeroSpec }) {
  // The workspace's Reduce motion switch (.rm) shows the finished picture at once.
  const still = typeof document !== "undefined" && Boolean(document.querySelector(".rm"));
  const t = (d: number, delay = 0) => (still ? { duration: 0 } : { duration: d, delay, ease });
  return (
    <div className="hero-r">
      <div className="hero-fig">
        <motion.b className="num" style={{ color: TONE[spec.tone ?? ""] ?? "var(--text)" }} initial={still ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={t(0.5)}>{spec.figure}</motion.b>
        {spec.versus ? <span className="num">{spec.versus}</span> : null}
      </div>
      {spec.line ? <p className="hero-line">{spec.line}</p> : null}
      {spec.lines?.length ? <Lines lines={spec.lines} t={t} still={still} /> : null}
      {spec.bars?.length ? (
        <div className="hero-bars">
          {spec.bars.map((b, i) => {
            const top = Math.max(...spec.bars!.map((x) => x.value), 1e-9);
            return (
              <button key={b.label} type="button" onClick={() => openQuickLook(b.label)} title={`${b.label} ${b.value.toFixed(1)}`}>
                <motion.i style={{ height: `${Math.max(2, (b.value / top) * 100)}%`, transformOrigin: "bottom" }} initial={still ? false : { scaleY: 0 }} animate={{ scaleY: 1 }} transition={t(0.6, i * 0.03)} />
                <span>{b.label}</span>
              </button>
            );
          })}
        </div>
      ) : null}
      {spec.stack?.length ? (
        <div className="hero-stack">
          <div className="hero-stack-bar">
            {spec.stack.map((s, i) => <motion.i key={s.label} style={{ flexGrow: s.value, background: STACK[i % STACK.length], transformOrigin: "left" }} initial={still ? false : { scaleX: 0 }} animate={{ scaleX: 1 }} transition={t(0.6, i * 0.05)} title={`${s.label} ${s.value}`} />)}
          </div>
          <div className="hero-stack-key">{spec.stack.map((s, i) => <span key={s.label}><i style={{ background: STACK[i % STACK.length] }} />{s.label} <b className="num">{s.value}</b></span>)}</div>
        </div>
      ) : null}
    </div>
  );
}

function Lines({ lines, t, still }: { lines: NonNullable<HeroSpec["lines"]>; t: (d: number, delay?: number) => object; still: boolean }) {
  const all = lines.flatMap((l) => l.values);
  const lo = Math.min(...all), hi = Math.max(...all), n = Math.max(...lines.map((l) => l.values.length));
  const y = (v: number) => 100 - ((v - lo) / (hi - lo || 1)) * 92 - 4;
  const d = (v: number[]) => v.map((p, i) => `${i ? "L" : "M"}${(i / Math.max(1, n - 1)) * 1000},${y(p).toFixed(2)}`).join("");
  return (
    <div className="hero-lines">
      <svg viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" aria-label={lines.map((l) => l.label).join(" against ")}>
        {lines.map((l, i) => <motion.path key={l.label} d={d(l.values)} fill="none" stroke={l.color} strokeWidth={i ? 1.25 : 2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" initial={still ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={t(1.4, i * 0.15)} />)}
      </svg>
      <div className="hero-key">{lines.map((l) => <span key={l.label}><i style={{ background: l.color }} />{l.label}</span>)}</div>
    </div>
  );
}
