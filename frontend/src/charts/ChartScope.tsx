"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { parseDate } from "./core";

export type ChartEvent = { date: string; label: string; kind?: string };
type Scope = { range: [number, number] | null; setRange: (range: [number, number] | null) => void; linked: boolean; setLinked: (linked: boolean) => void; events: ChartEvent[] };
const Context = createContext<Scope | null>(null);

/** A result owns its annotations and zoom; changing runs remounts this provider. */
export function ChartScope({ events: raw, children }: { events?: unknown; children: ReactNode }) {
  const [range, setRange] = useState<[number, number] | null>(null);
  const [linked, setLinked] = useState(true);
  const events = useMemo(() => Array.isArray(raw) ? raw.flatMap((event) => {
    if (!event || typeof event !== "object" || typeof event.label !== "string") return [];
    const t = parseDate(event.date);
    return t === null ? [] : [{ date: new Date(t).toISOString(), label: event.label, ...(typeof event.kind === "string" ? { kind: event.kind } : {}) }];
  }) : [], [raw]);
  const value = useMemo(() => ({ range, setRange, linked, setLinked, events }), [range, linked, events]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export const useChartScope = () => useContext(Context);
