"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Title } from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { Check, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { searchSymbols, usePopular, type SymbolHit } from "@/kit/QuickLookData";
import { SymbolRow } from "./SearchOverlay";
import "./search.css";

/** Universe picker: a field that opens a full search of every name we hold; picks are added by the caller and the search stays open for more. */
export function SymbolPick({ onPick, exclude = [] }: { onPick: (ticker: string) => void; exclude?: string[] }) {
  const [open, setOpen] = useState(false);
  const [seed, setSeed] = useState("");
  const start = (text = "") => { setSeed(text); setOpen(true); };
  return (
    <>
      <button type="button" className="tokens sp-trigger" aria-haspopup="dialog" onClick={() => start()}
        onKeyDown={(e) => { if (e.key.length === 1 && !e.metaKey && !e.ctrlKey) { e.preventDefault(); start(e.key); } }}>
        <Search size={13} aria-hidden />
        <span>Search a ticker or company</span>
        <span className="kbd">/</span>
      </button>
      {open ? <PickDialog seed={seed} onClose={() => setOpen(false)} onPick={onPick} exclude={exclude} /> : null}
    </>
  );
}

function PickDialog({ seed, onClose, onPick, exclude }: { seed: string; onClose: () => void; onPick: (t: string) => void; exclude: string[] }) {
  const [text, setText] = useState(seed);
  const [q, setQ] = useState(seed.trim());
  const [exchange, setExchange] = useState<string | null>(null);
  const [added, setAdded] = useState<string[]>([]);
  useEffect(() => { const t = setTimeout(() => setQ(text.trim()), 120); return () => clearTimeout(t); }, [text]);
  const popular = usePopular();
  const typing = q.length > 0 || exchange !== null;
  const found = useQuery({ queryKey: ["symbol-search", q, exchange], queryFn: ({ signal }) => searchSymbols(q, exchange, signal), enabled: typing, placeholderData: keepPreviousData, retry: false });
  const hits: SymbolHit[] = typing ? found.data?.results ?? [] : popular.data?.results ?? [];
  const have = new Set([...exclude, ...added]);
  const pick = (t: string) => { if (have.has(t)) return; onPick(t); setAdded((a) => [...a, t]); };
  // The dialog renders in a portal, outside the shell, so it borrows the shell's theme classes.
  const theme = typeof document === "undefined" ? "" : (document.querySelector(".ws")?.className ?? "").replace(/^ws\b/, "");

  return (
    <Command.Dialog open onOpenChange={(o) => { if (!o) onClose(); }} label="Add symbols" shouldFilter={false}
      overlayClassName={`cmdk-overlay ${theme}`} contentClassName={`cmdk so ${theme}`}>
      <Title className="sr-only">Add symbols</Title>
      <div className="so-input">
        <Search size={16} strokeWidth={1.75} aria-hidden />
        <Command.Input value={text} onValueChange={setText} placeholder="Ticker or company" autoFocus
          onKeyDown={(e) => { if (e.key === "Enter" && !hits.length && text.trim() && q === text.trim() && found.isFetched && !found.isFetching) { e.preventDefault(); pick(text.trim().toUpperCase()); setText(""); } }} />
        <span className="kbd">esc</span>
      </div>
      {(popular.data?.exchanges.length ?? 0) > 1 ? (
        <div className="so-chips" role="group" aria-label="Exchange">
          <button className="pill" aria-pressed={exchange === null} onClick={() => setExchange(null)}>All</button>
          {popular.data!.exchanges.map((x) => <button key={x.name} className="pill" aria-pressed={exchange === x.name} onClick={() => setExchange(exchange === x.name ? null : x.name)}>{x.name}<span className="num">{x.count.toLocaleString()}</span></button>)}
        </div>
      ) : null}
      <Command.List>
        {typing && found.isFetching && !found.data ? <div className="so-state" role="status">Searching…</div> : null}
        {found.error && typing ? <div className="so-state err" role="alert">{(found.error as Error).message}</div> : null}
        <Command.Empty>{found.isFetching ? null : text.trim() ? <>No match. Press <span className="kbd">↵</span> to add {text.trim().toUpperCase()} as typed.</> : "Type a ticker or company"}</Command.Empty>
        {hits.length ? (
          <Command.Group heading={typing ? `${found.data?.total.toLocaleString() ?? hits.length} matches` : "Popular"}>
            {hits.map((h) => (
              <Command.Item key={h.ticker} value={h.ticker} onSelect={() => pick(h.ticker)} className="so-item" aria-disabled={have.has(h.ticker)}>
                <SymbolRow hit={h} />
                {have.has(h.ticker) ? <Check size={15} className="sp-added" aria-label="Added" /> : null}
              </Command.Item>
            ))}
          </Command.Group>
        ) : null}
      </Command.List>
      <div className="sp-foot">
        <span>{added.length ? `${added.length} added: ${added.slice(-6).join(", ")}${added.length > 6 ? "…" : ""}` : <><span className="kbd">↵</span> adds the highlighted name</>}</span>
        <button className="btn sm primary" onClick={onClose}>Done</button>
      </div>
    </Command.Dialog>
  );
}
