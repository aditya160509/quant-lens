"use client";

import { Eye, EyeOff, Plus, Redo2, Undo2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { create } from "zustand";
import { useJob, useRuns } from "./api";
import { redo, undo, useFormHistory } from "./formHistory";
import { lab } from "./lab";
import type { FormState } from "./StudyForm";
import type { InputSpec } from "./types";

const BOUND = /_(min|max|top)$/;
const SIDES = ["min", "max", "top"] as const;
type Side = (typeof SIDES)[number];
const WORD: Record<Side, string> = { min: "Above", max: "Below", top: "Top N" };

/** A numeric field that is one side of a min/max/top chip. */
export const isRangeField = (f: InputSpec) => f.type === "number" && BOUND.test(f.key);

const blank = (v: unknown) => v === undefined || v === null || v === "";

/** Values of chips switched off, kept so they can be switched back on. Keyed by study, then metric. */
const useOff = create<{ off: Record<string, Record<string, Partial<Record<Side, unknown>>>> }>(() => ({ off: {} }));

/** Range filters as chips: greater, less, between (both) or top N. Each shows what it removed in the last run and can be switched off. */
export function FilterChips({ scope, fields, form, setForm }: {
  scope: string;
  fields: InputSpec[];
  form: FormState;
  setForm: (updater: (cur: FormState) => FormState) => void;
}) {
  const [query, setQuery] = useState("");
  const [added, setAdded] = useState<string[]>([]);
  const off = useOff((s) => s.off[scope]) ?? NONE;
  const canUndo = useFormHistory((h) => (h.past[scope] ?? []).length > 0);
  const canRedo = useFormHistory((h) => (h.future[scope] ?? []).length > 0);
  const jobId = useRuns((s) => s.runs.find((r) => r.featureId === scope && r.status === "completed")?.jobId) ?? null;
  const counts = lab().funnel?.(useJob(jobId).data?.result) ?? NONE_COUNTS;
  const metrics = useMemo(() => {
    const byName = new Map<string, { name: string; label: string; help?: string; top: boolean }>();
    for (const f of fields) {
      const name = f.key.replace(BOUND, "");
      const cur = byName.get(name);
      byName.set(name, { name, label: f.label.replace(/ (Min|Max|Top)$/, ""), help: f.help, top: (cur?.top ?? false) || f.key.endsWith("_top") });
    }
    return [...byName.values()];
  }, [fields]);

  const isSet = (name: string) => SIDES.some((s) => !blank(form[`${name}_${s}`]));
  const active = metrics.filter((m) => added.includes(m.name) || isSet(m.name) || off[m.name]);
  const q = query.trim().toLowerCase();
  const matches = q ? metrics.filter((m) => !active.includes(m) && m.label.toLowerCase().includes(q)) : [];
  const patch = (name: string, values: Partial<Record<Side, unknown>>) => setForm((cur) => ({ ...cur, ...Object.fromEntries(SIDES.map((s) => [`${name}_${s}`, values[s] ?? ""])) }));
  const stash = (name: string, values: Partial<Record<Side, unknown>> | null) => useOff.setState((s) => {
    const { [name]: _, ...rest } = s.off[scope] ?? {};
    void _;
    return { off: { ...s.off, [scope]: values ? { ...rest, [name]: values } : rest } };
  });

  const add = (name: string) => { setAdded((cur) => [...cur, name]); setQuery(""); };
  const remove = (name: string) => { setAdded((cur) => cur.filter((x) => x !== name)); stash(name, null); patch(name, {}); };
  const toggle = (name: string) => {
    if (off[name]) { patch(name, off[name]); stash(name, null); return; }
    stash(name, Object.fromEntries(SIDES.map((s) => [s, form[`${name}_${s}`]]).filter(([, v]) => !blank(v))));
    patch(name, {});
  };
  const bound = (name: string, side: Side, label: string) => (
    <input className="input num" inputMode="decimal" style={{ width: 70, height: 26 }} placeholder={WORD[side]} aria-label={`${label} ${WORD[side]}`} disabled={Boolean(off[name])}
      value={String(form[`${name}_${side}`] ?? "")} onChange={(e) => { const v = e.target.value; setForm((cur) => ({ ...cur, [`${name}_${side}`]: v })); }} />
  );

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 2 }}>
        <button type="button" className="btn sm ghost" aria-label="Undo" disabled={!canUndo} onClick={() => undo(scope)}><Undo2 size={12} /></button>
        <button type="button" className="btn sm ghost" aria-label="Redo" disabled={!canRedo} onClick={() => redo(scope)}><Redo2 size={12} /></button>
      </div>
      {active.map((m) => (
        <div key={m.name} title={m.help} style={{ display: "flex", alignItems: "center", gap: 6, opacity: off[m.name] ? 0.5 : 1 }}>
          <span style={{ flex: 1, minWidth: 0, fontSize: 12, color: "var(--text-2)" }}>{m.label}</span>
          {counts[m.name] ? <span className="num" style={{ fontSize: 11, color: "var(--text-3)" }} title={`${counts[m.name].remaining.toLocaleString()} left`}>{counts[m.name].bottleneck ? "● " : ""}−{counts[m.name].removed.toLocaleString()}</span> : null}
          {bound(m.name, "min", m.label)}
          {bound(m.name, "max", m.label)}
          {m.top ? bound(m.name, "top", m.label) : null}
          <button type="button" className="btn sm ghost" aria-label={`${off[m.name] ? "Enable" : "Disable"} ${m.label}`} aria-pressed={Boolean(off[m.name])} onClick={() => toggle(m.name)}>{off[m.name] ? <EyeOff size={12} /> : <Eye size={12} />}</button>
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

const NONE: Record<string, Partial<Record<Side, unknown>>> = {};
const NONE_COUNTS: Record<string, { removed: number; remaining: number; bottleneck?: boolean }> = {};
