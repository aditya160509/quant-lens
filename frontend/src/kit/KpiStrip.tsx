"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

const NUM = /^([-+−]?)([\d,]*\.?\d+)(%|x|×)?$/;

/** A plain figure ("1,234", "-0.302", "71.2%") rolls from its last value to the new one; anything else renders as is. */
function Roll({ value }: { value: ReactNode }) {
  const m = typeof value === "string" || typeof value === "number" ? String(value).match(NUM) : null;
  const target = m ? Number(m[2].replace(/,/g, "")) * (m[1] === "-" || m[1] === "−" ? -1 : 1) : null;
  const dp = m ? (m[2].split(".")[1] ?? "").length : 0;
  const comma = m ? m[2].includes(",") : false;
  const from = useRef(0);
  const [shown, setShown] = useState<number | null>(target);
  useEffect(() => {
    if (target === null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(target); from.current = target; return; }
    const a = from.current, t0 = performance.now();
    let id = 0;
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / 600), e = 1 - (1 - k) ** 3; setShown(a + (target - a) * e); if (k < 1) id = requestAnimationFrame(tick); else from.current = target; };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [target]);
  if (!m || target === null || shown === null) return <>{value}</>;
  const body = Math.abs(shown).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp, useGrouping: comma });
  return <>{shown < 0 || (m[1] && target < 0) ? m[1] || "-" : m[1] === "+" ? "+" : ""}{body}{m[3] ?? ""}</>;
}

export type Kpi = { label: string; value: ReactNode; tone?: string; title?: string; delta?: ReactNode; word?: boolean };

/** A row of headline numbers. `compact` is the smaller strip used inside an exhibit. */
export function KpiStrip({ items, compact }: { items: Kpi[]; compact?: boolean }) {
  if (compact) return (
    <div className="kpis-compact">
      {items.map((k) => <div key={k.label} title={k.title}><span>{k.label}</span><b className="num" style={k.tone ? { color: k.tone } : undefined}>{k.value}</b></div>)}
    </div>
  );
  return (
    <div className="kpis">
      {items.map((k) => (
        <div key={k.label} className="kpi">
          <div className="l" title={k.title ?? k.label}>{k.label}</div>
          {k.delta ? <div className="kpi-delta num" title="Change since the previous run of this page">{k.delta}</div> : null}
          <div className={`v${k.word ? " word" : ""}`} style={k.tone ? { color: k.tone } : undefined}><Roll value={k.value} /></div>
        </div>
      ))}
    </div>
  );
}
