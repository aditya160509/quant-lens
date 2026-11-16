"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type Command = { id: string; label: string; group: string; hint?: string; ask?: string; run: (answer?: string) => void };

/** ⌘⇧P: one list of actions, filtered as you type, Enter runs the highlighted one. */
export function Palette({ open, onClose, commands }: { open: boolean; onClose: () => void; commands: Command[] }) {
  const [q, setQ] = useState("");
  const [at, setAt] = useState(0);
  const [asking, setAsking] = useState<Command | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const shown = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return commands.filter((c) => words.every((w) => `${c.group} ${c.label}`.toLowerCase().includes(w))).slice(0, 40);
  }, [q, commands]);
  useEffect(() => { if (open) { setQ(""); setAt(0); setAsking(null); setTimeout(() => input.current?.focus(), 0); } }, [open]);
  useEffect(() => setAt(0), [q]);
  if (!open) return null;
  const go = (c?: Command) => {
    if (!c) return;
    if (asking) { if (q.trim()) { onClose(); asking.run(q.trim()); } return; }
    if (c.ask) { setAsking(c); setQ(""); return; }
    onClose(); c.run();
  };
  return (
    <div className="pl-back" role="presentation" onMouseDown={onClose}>
      <div className="pl" role="dialog" aria-label="Commands" onMouseDown={(e) => e.stopPropagation()}>
        <input ref={input} className="pl-q" value={q} placeholder={asking?.ask ?? "Type a command or template"} aria-label={asking?.ask ?? "Command"}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") { e.preventDefault(); setAt((i) => Math.min(shown.length - 1, i + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setAt((i) => Math.max(0, i - 1)); }
            else if (e.key === "Enter") { e.preventDefault(); go(asking ?? shown[at]); }
          }} />
        {asking ? <p className="pl-ask">{asking.label} · Enter to apply, Esc to cancel</p> : (
        <div className="pl-list" role="listbox" aria-label="Commands">
          {shown.map((c, i) => (
            <div key={c.id} role="option" tabIndex={-1} aria-selected={i === at} className={i === at ? "on" : ""} onMouseEnter={() => setAt(i)} onClick={() => go(c)} onKeyDown={(e) => e.key === "Enter" && go(c)}>
              <span className="pl-g">{c.group}</span><span>{c.label}</span>{c.hint ? <kbd>{c.hint}</kbd> : null}
            </div>
          ))}
          {!shown.length ? <div className="pl-none">No match</div> : null}
        </div>
        )}
      </div>
    </div>
  );
}
