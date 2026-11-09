"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { searchSymbols } from "@/kit/QuickLookData";
import { SymbolRow } from "./SearchOverlay";

/** Universe picker: search any name we hold by ticker or company; picks are added by the caller. */
export function SymbolPick({ onPick, exclude = [] }: { onPick: (ticker: string) => void; exclude?: string[] }) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [at, setAt] = useState(0);
  const id = useId();
  useEffect(() => { const t = setTimeout(() => setQ(text.trim()), 120); return () => clearTimeout(t); }, [text]);
  const res = useQuery({ queryKey: ["symbol-search", q, null], queryFn: ({ signal }) => searchSymbols(q, null, signal), enabled: q.length > 0, placeholderData: keepPreviousData, retry: false });
  const hits = (res.data?.results ?? []).filter((h) => !exclude.includes(h.ticker)).slice(0, 8);
  const pick = (t: string) => { onPick(t); setText(""); setQ(""); setAt(0); };
  return (
    <div style={{ position: "relative" }}>
      <div className="tokens">
        <Search size={13} style={{ color: "var(--text-3)", marginLeft: 4 }} aria-hidden />
        <input value={text} placeholder="Search a ticker or company" aria-label="Search names" role="combobox" aria-expanded={hits.length > 0} aria-controls={id} aria-activedescendant={hits[at] ? `${id}-${at}` : undefined}
          onChange={(e) => { setText(e.target.value); setAt(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setAt((a) => Math.min(a + 1, hits.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setAt((a) => Math.max(a - 1, 0)); }
            if (e.key === "Enter" && text.trim()) { e.preventDefault(); pick(hits[at]?.ticker ?? text.trim().toUpperCase()); }
            if (e.key === "Escape") setText("");
          }} />
      </div>
      {q && hits.length ? (
        <div className="menu so-menu" role="listbox" id={id}>
          {hits.map((h, i) => (
            <button key={h.ticker} id={`${id}-${i}`} type="button" role="option" aria-selected={i === at} onMouseEnter={() => setAt(i)} onClick={() => pick(h.ticker)}><SymbolRow hit={h} /></button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
