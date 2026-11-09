"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { get } from "@/modules/research/api";
import type { InputSpec } from "@/modules/research/types";

export type Facets = Record<string, { name: string; count: number }[]>;
export const useFacets = () => useQuery({ queryKey: ["screener", "facets"], queryFn: () => get<Facets>("/facets"), staleTime: 300_000, retry: false });

/** A value arrives as a list from this control, or as one name from a link or the search overlay. */
export const picked = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : !v || String(v).toLowerCase() === "all" ? [] : [String(v)]);

/** "In" chip: pick any number of values, each listed with how many names hold it. */
export function InFilter({ field, value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const facets = useFacets();
  const [q, setQ] = useState("");
  const chosen = picked(value);
  const set = (next: string[]) => onChange(next.length ? next : "all");
  const hits = (facets.data?.[field.key] ?? []).filter((o) => !chosen.includes(o.name) && o.name.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {chosen.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {chosen.map((c) => <span key={c} className="token">{c}<button type="button" aria-label={`Remove ${c}`} onClick={() => set(chosen.filter((x) => x !== c))}><X size={10} /></button></span>)}
        </div>
      ) : null}
      <input className="input" value={q} placeholder={`${field.label} in…`} aria-label={`${field.label} in`} onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) { e.preventDefault(); set([...chosen, hits[0].name]); setQ(""); } }} />
      {q || chosen.length === 0 ? (
        <div role="listbox" aria-label={`${field.label} values`} style={{ maxHeight: 160, overflowY: "auto", display: "grid" }}>
          {facets.isLoading ? <span className="hint">Loading…</span> : hits.map((o) => (
            <button key={o.name} type="button" role="option" aria-selected={false} className="btn sm ghost" style={{ justifyContent: "space-between" }} onClick={() => { set([...chosen, o.name]); setQ(""); }}>
              {o.name}<span className="num" style={{ color: "var(--text-3)" }}>{o.count.toLocaleString()}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
