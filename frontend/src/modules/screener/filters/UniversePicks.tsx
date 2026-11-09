"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { get, uploadFile } from "@/modules/research/api";
import { send } from "../api";
import { useWatchlists } from "../watchlists";

type Saved = { universe_id: string; name: string; symbols: string[]; count: number };

/** Universe sources beyond typing: a CSV file, a saved universe, a watchlist; and saving the current list. */
export function UniversePicks({ tickers, onChange }: { tickers: string[]; onChange: (csv: string) => void }) {
  const qc = useQueryClient();
  const saved = useQuery({ queryKey: ["screener", "universes"], queryFn: () => get<{ universes: Saved[] }>("/universes"), retry: false });
  const lists = useWatchlists((s) => s.lists);
  const file = useRef<HTMLInputElement>(null);
  const [name, setName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : "Failed");
  const merge = (list: string[]) => { setError(null); onChange([...new Set([...tickers, ...list])].join(",")); };
  const save = () => {
    const label = name?.trim();
    if (!label) return;
    send<Saved>("PUT", `/universes/u${Date.now().toString(36)}`, { name: label, symbols: tickers }).then(() => { setName(null); return qc.invalidateQueries({ queryKey: ["screener", "universes"] }); }).catch(fail);
  };
  const options = [...(saved.data?.universes ?? []).map((u) => ({ key: `u:${u.universe_id}`, label: `${u.name} (${u.count})`, symbols: u.symbols })), ...Object.entries(lists).filter(([, l]) => l.length).map(([n, l]) => ({ key: `w:${n}`, label: `Watchlist ${n} (${l.length})`, symbols: l }))];
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <select className="input" style={{ flex: 1 }} aria-label="Saved universe or watchlist" value="" onChange={(e) => { const o = options.find((x) => x.key === e.target.value); if (o) merge(o.symbols); }}>
          <option value="">Add a saved list</option>
          {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select>
        <button type="button" className="btn sm ghost" onClick={() => file.current?.click()}><Upload size={12} />CSV</button>
        <button type="button" className="btn sm ghost" disabled={!tickers.length} onClick={() => setName("")}><Save size={12} />Save</button>
        <input ref={file} type="file" accept=".csv,text/csv" hidden aria-label="Universe CSV" onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) uploadFile("universe", f).then((r) => { merge((r as unknown as Saved).symbols); return qc.invalidateQueries({ queryKey: ["screener", "universes"] }); }).catch(fail);
        }} />
      </div>
      {name !== null ? <input className="input" autoFocus value={name} placeholder="Universe name, then Enter" aria-label="Universe name" onChange={(e) => setName(e.target.value)} onBlur={() => setName(null)} onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setName(null); }} /> : null}
      {error ? <div className="err" role="alert">{error}</div> : null}
    </div>
  );
}
