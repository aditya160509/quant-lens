"use client";

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

export function HeroResult({ spec }: { spec: HeroSpec }) {
  return (
    <div className="hero-r">
      <div className="hero-fig">
        <b className="num" style={{ color: TONE[spec.tone ?? ""] ?? "var(--text)" }}>{spec.figure}</b>
        {spec.versus ? <span className="num">{spec.versus}</span> : null}
      </div>
      {spec.line ? <p className="hero-line">{spec.line}</p> : null}
      {spec.lines?.length ? <Lines lines={spec.lines} /> : null}
      {spec.bars?.length ? (
        <div className="hero-bars">
          {spec.bars.map((b, i) => {
            const top = Math.max(...spec.bars!.map((x) => x.value), 1e-9);
            return (
              <button key={b.label} type="button" onClick={() => openQuickLook(b.label)} title={`${b.label} ${b.value.toFixed(1)}`}>
                <i style={{ height: `${Math.max(2, (b.value / top) * 100)}%`, transformOrigin: "bottom" }} />
                <span>{b.label}</span>
              </button>
            );
          })}
        </div>
      ) : null}
      {spec.stack?.length ? (
        <div className="hero-stack">
          <div className="hero-stack-bar">
            {spec.stack.map((s, i) => <i key={s.label} style={{ flexGrow: s.value, background: STACK[i % STACK.length], transformOrigin: "left" }} title={`${s.label} ${s.value}`} />)}
          </div>
          <div className="hero-stack-key">{spec.stack.map((s, i) => <span key={s.label}><i style={{ background: STACK[i % STACK.length] }} />{s.label} <b className="num">{s.value}</b></span>)}</div>
        </div>
      ) : null}
    </div>
  );
}

function Lines({ lines }: { lines: NonNullable<HeroSpec["lines"]> }) {
  const all = lines.flatMap((l) => l.values);
  const lo = Math.min(...all), hi = Math.max(...all), n = Math.max(...lines.map((l) => l.values.length));
  const y = (v: number) => 100 - ((v - lo) / (hi - lo || 1)) * 92 - 4;
  const d = (v: number[]) => v.map((p, i) => `${i ? "L" : "M"}${(i / Math.max(1, n - 1)) * 1000},${y(p).toFixed(2)}`).join("");
  return (
    <div className="hero-lines">
      <svg viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" aria-label={lines.map((l) => l.label).join(" against ")}>
        {lines.map((l, i) => <path key={l.label} d={d(l.values)} fill="none" stroke={l.color} strokeWidth={i ? 1.25 : 2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />)}
      </svg>
      <div className="hero-key">{lines.map((l) => <span key={l.label}><i style={{ background: l.color }} />{l.label}</span>)}</div>
    </div>
  );
}
