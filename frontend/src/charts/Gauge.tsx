"use client";

import { motion } from "framer-motion";

type Zone = { to: number; color: string; label: string };

/** Semicircular gauge with coloured zones and an animated needle. Values beyond the scale pin to the ends. */
export function Gauge({ value, min = 0, max = 100, zones, label, sub }: { value: number; min?: number; max?: number; zones: Zone[]; label: string; sub?: string }) {
  const W = 260, H = 150, cx = W / 2, cy = 132, R = 104;
  const frac = (v: number) => Math.max(0, Math.min(1, (v - min) / (max - min)));
  const pt = (f: number, r = R) => [cx - r * Math.cos(Math.PI * f), cy - r * Math.sin(Math.PI * f)] as const;
  const arc = (a: number, b: number) => {
    const [x0, y0] = pt(a), [x1, y1] = pt(b);
    return `M${x0},${y0} A${R},${R} 0 0 1 ${x1},${y1}`;
  };
  const segs = zones.map((z, i) => ({ from: i ? frac(zones[i - 1].to) : 0, to: frac(z.to), color: z.color }));
  const f = frac(value);
  const zone = zones.find((z) => value <= z.to) ?? zones[zones.length - 1];
  const angle = -90 + f * 180;

  return (
    <div style={{ display: "grid", justifyItems: "center" }}>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ maxWidth: 320 }} role="img" aria-label={`${label}: ${value.toFixed(0)}`}>
        {segs.map((s, i) => <path key={i} d={arc(s.from + 0.004, s.to - 0.004)} stroke={s.color} strokeOpacity={0.85} strokeWidth={12} fill="none" strokeLinecap="butt" />)}
        <motion.g initial={{ rotate: -90 }} animate={{ rotate: angle }} transition={{ type: "spring", stiffness: 60, damping: 14 }} style={{ originX: `${cx}px`, originY: `${cy}px` }}>
          <line x1={cx} y1={cy} x2={cx} y2={cy - R + 18} stroke="var(--text)" strokeWidth={2.5} strokeLinecap="round" />
        </motion.g>
        <circle cx={cx} cy={cy} r={6} fill="var(--text)" />
        <text x={cx} y={cy - 34} textAnchor="middle" fontSize={30} fontWeight={600} fill="var(--text)" style={{ fontFamily: "var(--mono)", letterSpacing: "-0.04em" }}>{value.toFixed(0)}</text>
      </svg>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: -4 }}>
        <span className="chip" style={{ color: zone.color, background: `color-mix(in oklch, ${zone.color} 16%, transparent)`, boxShadow: "none" }}>{zone.label}</span>
        <span style={{ color: "var(--text-3)", fontSize: 12 }}>{label}</span>
      </div>
      {sub ? <p style={{ marginTop: 8, color: "var(--text-3)", fontSize: 12, textAlign: "center", maxWidth: 300 }}>{sub}</p> : null}
    </div>
  );
}
