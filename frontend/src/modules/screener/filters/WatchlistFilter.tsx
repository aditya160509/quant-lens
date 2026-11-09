"use client";

import { X } from "lucide-react";
import type { InputSpec } from "@/modules/research/types";
import { useWatchlists } from "../watchlists";

/** Keep only the names of one watchlist. */
export function WatchlistFilter({ value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const lists = useWatchlists((s) => s.lists);
  const names = Object.keys(lists).filter((n) => lists[n].length);
  const current = names.find((n) => lists[n].join(",") === String(value ?? ""));
  if (!names.length) return <div className="hint">Star a name in the results to start a watchlist.</div>;
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <select className="input" aria-label="Watchlist" value={current ?? ""} onChange={(e) => onChange(e.target.value ? lists[e.target.value].join(",") : "")}>
        <option value="">Any name</option>
        {names.map((n) => <option key={n} value={n}>{n} ({lists[n].length})</option>)}
      </select>
      {value ? <button type="button" className="btn sm ghost" aria-label="Clear watchlist filter" onClick={() => onChange("")}><X size={12} /></button> : null}
    </div>
  );
}
