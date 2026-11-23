"use client";

import { Star } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { studio } from "../api";

export type IndicatorInfo = { name: string; title: string; overlay: boolean; inputs: Record<string, [number, number, number, number]>; outputs: string[] };
const FAV_KEY = "studio:indicators:fav";
const readFav = (): string[] => { try { return JSON.parse(localStorage.getItem(FAV_KEY) ?? "[]"); } catch { return []; } };

/** `self.<var> = self.use(ta.Name, input=default, ...)` at the end of Strategy.init (made when missing), plus `from studio import ta`. Null without a Strategy class. */
export function insertUse(code: string, ind: Pick<IndicatorInfo, "name" | "inputs">): string | null {
  const lines = code.split("\n");
  const cls = lines.findIndex((l) => /^class\s+Strategy\b.*:\s*$/.test(l));
  if (cls < 0) return null;
  const base = ind.name.replace(/([a-z])([A-Z])/g, "$1_$2").toLowerCase();
  let name = base;
  for (let i = 2; new RegExp(`self\\.${name}\\b`).test(code); i++) name = `${base}_${i}`;
  const args = Object.entries(ind.inputs).map(([k, v]) => `, ${k}=${v[0]}`).join("");
  const end = (from: number, indent: number) => { let last = from; for (let i = from + 1; i < lines.length; i++) { const l = lines[i]!; if (!l.trim()) continue; if (l.length - l.trimStart().length <= indent) break; last = i; } return last; };
  const body = lines.slice(cls + 1).find((l) => l.trim()), step = body ? body.length - body.trimStart().length : 4;
  const init = lines.findIndex((l, i) => i > cls && i <= end(cls, 0) && /^\s+def\s+init\s*\(\s*self\b/.test(l));
  const use = `self.${name} = self.use(ta.${ind.name}${args})`;
  if (init >= 0) {
    const pad = lines[init]!.length - lines[init]!.trimStart().length + step;
    lines.splice(end(init, pad - step) + 1, 0, `${" ".repeat(pad)}${use}`);
  } else lines.splice(cls + 1, 0, `${" ".repeat(step)}def init(self, ctx):`, `${" ".repeat(2 * step)}${use}`, "");
  const out = lines.join("\n");
  return /^\s*(from\s+studio\s+import\s+.*\bta\b|import\s+studio\.ta)/m.test(out) ? out : `from studio import ta\n${/^(import|from)\s/.test(out) ? "" : "\n"}${out}`;
}

/** TradingView's indicator dialog for a code-first chart: search, favourites, overlays and oscillators; picking one writes the `self.use` line. */
export function IndicatorPicker({ onPick, onClose }: { onPick: (ind: IndicatorInfo) => void; onClose: () => void }) {
  const { data, error } = useQuery({ queryKey: ["studio", "indicators"], queryFn: () => studio<{ indicators: IndicatorInfo[] }>("GET", "/indicators"), staleTime: Infinity });
  const [q, setQ] = useState("");
  const [fav, setFav] = useState(readFav);
  const toggle = (n: string) => setFav((f) => { const next = f.includes(n) ? f.filter((x) => x !== n) : [...f, n]; try { localStorage.setItem(FAV_KEY, JSON.stringify(next)); } catch { /* blocked */ } return next; });
  const groups = useMemo(() => {
    const hit = (data?.indicators ?? []).filter((i) => !q || `${i.name} ${i.title}`.toLowerCase().includes(q.toLowerCase()));
    return [["Favourites", hit.filter((i) => fav.includes(i.name))], ["On price", hit.filter((i) => i.overlay)], ["Own pane", hit.filter((i) => !i.overlay)]] as const;
  }, [data, q, fav]);
  return (
    <div className="dv-ind" role="dialog" aria-label="Indicators">
      <header>
        <input className="input sm" autoFocus placeholder="Search" aria-label="Search indicators" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { const first = groups.flatMap(([, l]) => l)[0]; if (e.key === "Escape") onClose(); if (e.key === "Enter" && first) onPick(first); }} />
        <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>×</button>
      </header>
      {error ? <p className="dv-empty">{(error as Error).message}</p> : !data ? <p className="dv-empty">Loading</p> : (
        <div className="dv-ind-list">
          {groups.map(([label, list]) => list.length ? (
            <section key={label}><h5>{label}</h5>
              {list.map((i) => (
                <div key={i.name} className="dv-ind-row">
                  <button type="button" className="dv-ind-pick" onClick={() => onPick(i)} title={`Adds self.use(ta.${i.name}) to Strategy.init`}>
                    <b>{i.title}</b><code>{i.name}{Object.keys(i.inputs).length ? `(${Object.values(i.inputs).map((v) => v[0]).join(", ")})` : ""}</code>
                  </button>
                  <button type="button" className="icon-btn" aria-label={fav.includes(i.name) ? `Unstar ${i.title}` : `Star ${i.title}`} aria-pressed={fav.includes(i.name)} onClick={() => toggle(i.name)}><Star size={13} /></button>
                </div>
              ))}
            </section>
          ) : null)}
        </div>
      )}
    </div>
  );
}
