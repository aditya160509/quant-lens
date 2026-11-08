"use client";

import { useCrosshair, fmtDate } from "@/charts/core";
import { useDataWindow } from "@/charts/dataWindow";

/** TradingView-style data window: every mounted time-series chart's values at the hovered date. */
export function DataWindow() {
  const t = useCrosshair((s) => s.t);
  const entries = useDataWindow((s) => s.entries);
  const list = Object.values(entries);
  if (t === null) return null;
  return (
    <section style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)" }}>
    <h4 className="insp-h">Data window</h4>
    <div style={{ display: "grid", gap: 10, fontSize: 12 }}>
      <div className="num" style={{ color: "var(--text-2)", fontWeight: 600 }}>{fmtDate(t, true)}</div>
      {list.map((e) => {
        const vals = e.valueAt(t);
        return (
          <div key={e.chartId}>
            <div style={{ color: "var(--text-3)", marginBottom: 3 }}>{e.title}</div>
            {e.series.map((s, i) => (
              <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 6, padding: "1px 0" }}>
                <i style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
                <span style={{ color: "var(--text-2)" }}>{s.label}</span>
                <span className="num" style={{ marginLeft: "auto", fontFamily: "var(--mono)" }}>{vals[i] ?? "–"}</span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
    </section>
  );
}
