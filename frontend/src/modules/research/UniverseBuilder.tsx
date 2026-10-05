"use client";

import { useMemo, useState } from "react";
import { ClipboardPaste, Search, X } from "lucide-react";
import { Segmented } from "@/workspace/ui";
import { lab } from "./lab";
import { useUniverse } from "./api";

type Mode = "all" | "sectors" | "custom";

const NAMED = new Set(["us_equities", ""]);

/**
 * Builds the stock universe: the whole US equity file, whole sectors, or a hand-picked list
 * (search, paste from anywhere, remove). Writes either "us_equities" or a comma-separated list.
 */
export function UniverseBuilder({ value, onChange, maxSymbols, onMaxSymbols }: {
  value: string;
  onChange: (v: string) => void;
  maxSymbols?: number;
  onMaxSymbols?: (n: number) => void;
}) {
  const tokens = useMemo(() => value.split(",").map((s) => s.trim()).filter(Boolean), [value]);
  const initial: Mode = tokens.length === 0 || (tokens.length === 1 && NAMED.has(tokens[0])) ? "all" : "custom";
  const [mode, setMode] = useState<Mode>(initial);
  const [sectors, setSectors] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [paste, setPaste] = useState(false);
  const [pasted, setPasted] = useState("");
  const universe = useUniverse(true);
  const all = useMemo(() => universe.data ?? [], [universe.data]);
  const bySector = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of all) if (s.sector) m.set(s.sector, (m.get(s.sector) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);
  const known = useMemo(() => new Map(all.map((s) => [s.ticker, s])), [all]);
  const hits = useMemo(() => {
    const k = q.trim().toUpperCase();
    if (!k) return [];
    return all.filter((s) => s.ticker.startsWith(k)).slice(0, 8).concat(all.filter((s) => !s.ticker.startsWith(k) && s.ticker.includes(k)).slice(0, 4));
  }, [q, all]);

  const setSectorList = (next: string[]) => {
    setSectors(next);
    const list = all.filter((s) => s.sector && next.includes(s.sector)).map((s) => s.ticker);
    onChange(list.length ? list.join(",") : "us_equities");
  };
  const custom = tokens.filter((t) => !NAMED.has(t));
  const addTickers = (list: string[]) => {
    const merged = [...new Set([...custom, ...list.map((t) => t.toUpperCase())])];
    onChange(merged.join(","));
  };
  const unknown = custom.filter((t) => all.length && !known.has(t));
  const count = mode === "all" ? Math.min(maxSymbols ?? all.length, all.length || maxSymbols || 0) : custom.length;

  // A lab with a fixed default (ML) sends an empty list for it; Research sends the whole US market.
  const preset = lab().defaultUniverse;
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <Segmented<Mode> label="Universe source" value={mode} onChange={(m) => {
        setMode(m);
        if (m === "all") onChange(preset ? "" : "us_equities");
        if (m === "sectors") setSectorList(sectors);
      }} options={[{ value: "all", label: preset ? "Default" : "All US" }, { value: "sectors", label: "Sectors" }, { value: "custom", label: "Custom" }]} />

      {mode === "all" && preset ? <div className="hint">{preset}, all on one exchange calendar, so every held position has a return every day.</div> : null}
      {mode === "all" && !preset ? (
        <div style={{ display: "grid", gap: 6 }}>
          <div className="hint">US common stocks, ranked by how much price history the data has. The study uses the top names.</div>
          {onMaxSymbols && maxSymbols !== undefined ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 64px", gap: 10, alignItems: "center" }}>
              <input className="range" type="range" min={30} max={Math.max(2000, all.length ? Math.min(2000, all.length) : 2000)} step={10} value={maxSymbols}
                style={{ ["--fill" as string]: `${((maxSymbols - 30) / (2000 - 30)) * 100}%` }} onChange={(e) => onMaxSymbols(Number(e.target.value))} aria-label="Number of stocks" />
              <input className="input num" style={{ height: 28, textAlign: "right" }} value={maxSymbols} onChange={(e) => onMaxSymbols(Number(e.target.value) || 30)} aria-label="Number of stocks" />
            </div>
          ) : null}
        </div>
      ) : null}

      {mode === "sectors" ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {universe.isLoading ? <span className="hint">Loading sectors…</span> : bySector.map(([s, n]) => (
            <button key={s} type="button" className="pill" aria-pressed={sectors.includes(s)} onClick={() => setSectorList(sectors.includes(s) ? sectors.filter((x) => x !== s) : [...sectors, s])}>
              {s}<span className="num" style={{ marginLeft: 6, fontSize: 10.5, opacity: 0.7 }}>{n}</span>
            </button>
          ))}
        </div>
      ) : null}

      {mode === "custom" ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ position: "relative" }}>
            <div className="tokens">
              <Search size={13} style={{ color: "var(--text-3)", marginLeft: 4 }} />
              <input value={q} placeholder="Search and add tickers" aria-label="Search tickers" onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && q.trim()) { e.preventDefault(); addTickers([hits[0]?.ticker ?? q.trim()]); setQ(""); }
                  if (e.key === "Escape") setQ("");
                }} />
              <button type="button" className="btn sm ghost" onClick={() => setPaste((p) => !p)} title="Paste a list"><ClipboardPaste size={12} />Paste</button>
            </div>
            {hits.length ? (
              <div className="menu" role="listbox">
                {hits.map((h) => (
                  <button key={h.ticker} type="button" role="option" aria-selected={false} onClick={() => { addTickers([h.ticker]); setQ(""); }}>
                    <b>{h.ticker}</b><span>{h.sector ?? ""}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {paste ? (
            <div style={{ display: "grid", gap: 6 }}>
              <textarea className="input" rows={3} value={pasted} placeholder="AAPL, MSFT NVDA&#10;AMZN" onChange={(e) => setPasted(e.target.value)} />
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <button type="button" className="btn sm" onClick={() => setPaste(false)}>Cancel</button>
                <button type="button" className="btn sm primary" onClick={() => { addTickers(pasted.split(/[\s,;]+/).filter(Boolean)); setPasted(""); setPaste(false); }}>Add tickers</button>
              </div>
            </div>
          ) : null}
          {custom.length ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, maxHeight: 132, overflowY: "auto" }}>
              {custom.map((t) => (
                <span key={t} className="token" style={unknown.includes(t) ? { boxShadow: "inset 0 0 0 1px var(--down)", color: "var(--down)" } : undefined} title={known.get(t)?.sector ?? (unknown.includes(t) ? "Not in the data" : "")}>
                  {t}
                  <button type="button" aria-label={`Remove ${t}`} onClick={() => onChange(custom.filter((x) => x !== t).join(",") || "us_equities")}><X size={10} /></button>
                </span>
              ))}
            </div>
          ) : <div className="hint">Add at least 30 stocks for cross-sectional tests.</div>}
          {unknown.length ? <div className="err">{unknown.length} ticker{unknown.length > 1 ? "s are" : " is"} not in the data and will be rejected: {unknown.slice(0, 6).join(", ")}</div> : null}
        </div>
      ) : null}

      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--text-3)" }}>
        <span>{mode === "custom" ? "Custom list" : mode === "sectors" ? `${sectors.length} sector${sectors.length === 1 ? "" : "s"}` : preset ? "Default" : "Whole market"}</span>
        <span className="num">{mode === "all" && preset ? preset : `${count.toLocaleString()} stocks`}{mode === "sectors" && maxSymbols ? `, capped at ${maxSymbols}` : ""}</span>
      </div>
      {mode !== "all" && custom.length ? <button type="button" className="btn sm ghost" style={{ justifySelf: "start" }} onClick={() => { onChange(preset ? "" : "us_equities"); setSectors([]); setMode("all"); }}>{preset ? "Reset to the default" : "Reset to all US equities"}</button> : null}
    </div>
  );
}
