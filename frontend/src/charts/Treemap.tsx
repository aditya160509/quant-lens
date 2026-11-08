"use client";

import { hierarchy, treemap } from "d3";
import { useMemo, useState } from "react";
import { diverging, fmtTick, Svg, useWidth } from "./core";

type Item = { label: string; group: string; size: number; alternativeSize?: number; colorValue?: number; /** Extra colour lenses keyed by `colorModes`; values are signed and centred on zero. */ colors?: Record<string, number | undefined> };
type Node = { label: string; children?: Node[]; size?: number; colorValue?: number };
type ColorMode = { key: string; label: string };

/** Zoom from families/sectors into their members. Rectangles and labels encode magnitude; signed colour retains its sign. */
export function Treemap({ items, title, sizeLabel, alternativeSizeLabel, colorLabel, colorModes, colorScale = "diverging", colorAggregate = "sum", format = fmtTick, colorFormat = fmtTick }: {
  items: Item[]; title: string; sizeLabel: string; alternativeSizeLabel?: string; colorLabel?: string; colorModes?: ColorMode[]; /** Sequential for magnitudes that cannot be negative (importance); diverging for signed measures. */ colorScale?: "diverging" | "sequential"; /** A group takes the sum of its members' colour values (weights) or their mean (returns, ratios). */ colorAggregate?: "sum" | "mean"; format?: (v: number) => string; colorFormat?: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [group, setGroup] = useState<string | null>(null);
  const [alternate, setAlternate] = useState(false);
  const [colorMode, setColorMode] = useState(colorModes?.[0]?.key ?? "");
  const [inspect, setInspect] = useState<string | null>(null);
  const height = 280;
  const activeMode = colorModes?.find((m) => m.key === colorMode) ?? null;
  const activeColorLabel = activeMode?.label ?? colorLabel;
  const colorOf = (r: Item) => (activeMode ? r.colors?.[activeMode.key] : r.colorValue);
  const nodes = useMemo(() => {
    const clean = items.filter((r) => Number.isFinite(alternate ? r.alternativeSize : r.size) && Math.abs((alternate ? r.alternativeSize : r.size) ?? 0) > 0);
    const groups = [...new Set(clean.map((r) => r.group))];
    const leaves = (rows: Item[]): Node[] => rows.map((r) => ({ label: r.label, size: alternate ? r.alternativeSize : r.size, colorValue: colorOf(r) }));
    const children = group ? leaves(clean.filter((r) => r.group === group)) : groups.map((name) => {
      const rows = clean.filter((r) => r.group === name);
      const values = rows.map(colorOf);
      return { label: name, children: leaves(rows), colorValue: values.every((v) => v !== undefined && Number.isFinite(v)) ? (values as number[]).reduce((a, b) => a + b, 0) / (colorAggregate === "mean" ? values.length : 1) : undefined };
    });
    const root = hierarchy<Node>({ label: title, children }).sum((r) => Math.abs(r.size ?? 0)).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    return treemap<Node>().size([Math.max(1, width), height]).padding(3).round(true)(root).children ?? [];
  }, [items, alternate, group, width, title, activeMode, colorAggregate]);
  const max = Math.max(...nodes.map((n) => Math.abs(n.data.colorValue ?? 0)), 1e-12);
  const fillOf = (v: number) => colorScale === "sequential"
    ? `color-mix(in oklch, var(--accent) ${Math.round(Math.min(1, Math.abs(v) / max) * 72)}%, var(--panel-2))`
    : diverging(v / max);
  const description = (n: (typeof nodes)[number]) => `${n.data.label}: ${alternate ? alternativeSizeLabel : sizeLabel} ${format(n.value ?? 0)}${activeColorLabel ? `; ${activeColorLabel} ${n.data.colorValue === undefined ? "unavailable" : colorFormat(n.data.colorValue)}` : ""}`;
  return <div ref={ref} className="treemap-chart" onKeyDown={(e) => { if (e.key === "Escape") { setGroup(null); setInspect(null); } }} onContextMenu={(e) => { if (group) { e.preventDefault(); setGroup(null); setInspect(null); } }}>
    <nav aria-label={`${title} breadcrumb`} className="chart-mode-tabs"><button onClick={() => { setGroup(null); setInspect(null); }} aria-current={group === null ? "page" : undefined}>All groups</button>{group ? <span> / {group}</span> : null}</nav>
    {alternativeSizeLabel ? <div className="chart-mode-tabs" role="group" aria-label="Rectangle area"><button aria-pressed={!alternate} onClick={() => setAlternate(false)}>{sizeLabel}</button><button aria-pressed={alternate} onClick={() => setAlternate(true)}>{alternativeSizeLabel}</button></div> : null}
    {colorModes && colorModes.length > 1 ? <div className="chart-mode-tabs" role="group" aria-label="Rectangle colour"><span style={{ color: "var(--text-4)", alignSelf: "center" }}>Colour</span>{colorModes.map((m) => <button key={m.key} aria-pressed={m.key === colorMode} aria-label={`Colour ${m.label}`} onClick={() => { setColorMode(m.key); setInspect(null); }}>{m.label}</button>)}</div> : null}
    {nodes.length ? <Svg width={width} height={height} label={title} role="group">{nodes.map((n, i) => {
      const w = Math.max(0, n.x1 - n.x0), h = Math.max(0, n.y1 - n.y0);
      const desc = description(n);
      return <g key={n.data.label} role="button" tabIndex={0} aria-label={`${desc}${group ? "" : ". Open group"}`} onFocus={() => setInspect(desc)} onPointerEnter={() => setInspect(desc)} onClick={() => { if (!group) { setGroup(n.data.label); setInspect(null); } else setInspect(desc); }} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!group) { setGroup(n.data.label); setInspect(null); } else setInspect(desc); } }}>
        <title>{desc}</title><rect x={n.x0} y={n.y0} width={w} height={h} fill={n.data.colorValue === undefined ? `color-mix(in oklch, var(--c${i % 8 + 1}) 25%, var(--panel))` : fillOf(n.data.colorValue)} stroke="var(--line-3)" />
        {w > 65 && h > 40 ? <text x={n.x0 + 8} y={n.y0 + 20} fontSize={12} fill="var(--text)">{n.data.label.slice(0, Math.max(3, Math.floor((w - 16) / 7)))}<tspan x={n.x0 + 8} dy={18} fontSize={11}>{format(n.value ?? 0)}</tspan></text> : null}
      </g>;
    })}</Svg> : <p className="chart-empty">No positive magnitudes for this size measure.</p>}
    <p className="calendar-note" role="status">{inspect ?? `Area: absolute ${alternate ? alternativeSizeLabel : sizeLabel}.${activeColorLabel ? ` Colour: ${activeColorLabel}, ${colorScale === "sequential" ? "low to high" : "negative to positive"}; missing values use a neutral category tint.` : ""} ${group ? "Escape or right-click returns to all groups." : "Select a group to inspect its members."}`}</p>
  </div>;
}
