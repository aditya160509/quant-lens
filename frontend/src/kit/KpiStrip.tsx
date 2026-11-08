import type { ReactNode } from "react";

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
          <div className={`v${k.word ? " word" : ""}`} style={k.tone ? { color: k.tone } : undefined}>{k.value}</div>
        </div>
      ))}
    </div>
  );
}
