"use client";

import { Plus, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { FormState } from "./StudyForm";
import type { InputSpec } from "./types";

const BOUND = /_(min|max)$/;

/** A numeric field that is one side of a min/max pair. */
export const isRangeField = (f: InputSpec) => f.type === "number" && BOUND.test(f.key);

const blank = (v: unknown) => v === undefined || v === null || v === "";

/** Range filters as chips: search to add one, then set greater than, less than, or both for between. */
export function FilterChips({ fields, form, setForm }: {
  fields: InputSpec[];
  form: FormState;
  setForm: (updater: (cur: FormState) => FormState) => void;
}) {
  const [query, setQuery] = useState("");
  const [added, setAdded] = useState<string[]>([]);
  const metrics = useMemo(() => {
    const byName = new Map<string, { name: string; label: string; help?: string }>();
    for (const f of fields) {
      const name = f.key.replace(BOUND, "");
      if (!byName.has(name)) byName.set(name, { name, label: f.label.replace(/ (Min|Max)$/, ""), help: f.help });
    }
    return [...byName.values()];
  }, [fields]);

  const isSet = (name: string) => !blank(form[`${name}_min`]) || !blank(form[`${name}_max`]);
  const active = metrics.filter((m) => added.includes(m.name) || isSet(m.name));
  const q = query.trim().toLowerCase();
  const matches = q ? metrics.filter((m) => !active.includes(m) && m.label.toLowerCase().includes(q)) : [];

  const add = (name: string) => { setAdded((cur) => [...cur, name]); setQuery(""); };
  const remove = (name: string) => {
    setAdded((cur) => cur.filter((x) => x !== name));
    setForm((cur) => ({ ...cur, [`${name}_min`]: "", [`${name}_max`]: "" }));
  };
  const bound = (name: string, side: "min" | "max", word: string, label: string) => (
    <input className="input num" inputMode="decimal" style={{ width: 76, height: 26 }} placeholder={word} aria-label={`${label} ${word}`}
      value={String(form[`${name}_${side}`] ?? "")} onChange={(e) => { const v = e.target.value; setForm((cur) => ({ ...cur, [`${name}_${side}`]: v })); }} />
  );

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {active.map((m) => (
        <div key={m.name} title={m.help} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ flex: 1, minWidth: 0, fontSize: 12, color: "var(--text-2)" }}>{m.label}</span>
          {bound(m.name, "min", "Above", m.label)}
          {bound(m.name, "max", "Below", m.label)}
          <button type="button" className="btn sm ghost" aria-label={`Remove ${m.label}`} onClick={() => remove(m.name)}><X size={12} /></button>
        </div>
      ))}
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        <Plus size={13} style={{ position: "absolute", left: 8, color: "var(--text-3)" }} />
        <input className="input" style={{ width: "100%", paddingLeft: 26 }} placeholder={`Add filter (${metrics.length})`} aria-label="Add filter" value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && matches[0]) { e.preventDefault(); add(matches[0].name); } }} />
      </div>
      {matches.length ? (
        <div role="listbox" aria-label="Matching filters" style={{ maxHeight: 220, overflowY: "auto", display: "grid" }}>
          {matches.map((m) => (
            <button key={m.name} type="button" role="option" aria-selected={false} title={m.help} className="btn sm ghost" style={{ justifyContent: "flex-start" }} onClick={() => add(m.name)}>{m.label}</button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
