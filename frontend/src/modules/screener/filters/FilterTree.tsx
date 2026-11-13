"use client";

import { add, formatQuery, remove, update, type RuleGroupType, type RuleType } from "@react-querybuilder/core";
import { parseSQL } from "@react-querybuilder/core/parseSQL";
import { Eye, EyeOff, Plus, X } from "lucide-react";
import { useState } from "react";
import type { InputSpec } from "@/modules/research/types";
import { useFacets } from "./InFilter";

type Node = RuleGroupType | RuleType;
const OPERATORS = [">=", "<=", ">", "<", "=", "!=", "between", "in", "notIn"];
const EMPTY: RuleGroupType = { combinator: "and", rules: [] };
const CATEGORY = ["sector", "industry", "exchange", "country", "currency"];

const asTree = (v: unknown): RuleGroupType => {
  try {
    const t = typeof v === "string" && v.trim() ? JSON.parse(v) : v;
    return t && typeof t === "object" && "rules" in t ? (t as RuleGroupType) : EMPTY;
  } catch { return EMPTY; }
};
const REL_OPS = ["<", "<=", ">", ">=", "=", "!="];
const isRel = (n: Node) => "left" in n || "metric_vs_sector" in n;
const hasRel = (n: Node): boolean => ("rules" in n ? n.rules.some((r) => hasRel(r as Node)) : isRel(n));
/** Replaces the node at `path` with its merge of `p`, leaving the rest of the tree as it was. */
const patchAt = (g: RuleGroupType, path: number[], p: Record<string, unknown>): RuleGroupType => path.length
  ? { ...g, rules: g.rules.map((r, i) => (i !== path[0] ? r : "rules" in r || path.length > 1 ? patchAt(r as RuleGroupType, path.slice(1), p) : ({ ...r, ...p } as RuleType))) }
  : g;
const sql = (t: RuleGroupType) => (t.rules.length ? formatQuery(t, { format: "sql", parseNumbers: true }).replace(/^\(|\)$/g, "") : "");

/** Rules grouped with AND and OR, nested; the formula box and the tree stay in step both ways. */
export function FilterTree({ value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const tree = asTree(value);
  const metrics = useFacets().data?.metric ?? [];
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const commit = (next: RuleGroupType) => { setText(null); setError(null); onChange(next.rules.length ? next : ""); };
  const fields = [...metrics.map((m) => m.name), ...CATEGORY];
  const rel = (kind: "left" | "metric_vs_sector"): RuleType => ((kind === "left" ? { left: metrics[0]?.name ?? "pe", op: "<", right: `${metrics[0]?.name ?? "pe"}_sector_median` } : { metric_vs_sector: metrics[0]?.name ?? "pe", op: "<", value: 1 }) as unknown as RuleType);
  const rule = (): RuleType => ({ field: metrics[0]?.name ?? "pe", operator: ">=", value: "" });
  const group = (g: RuleGroupType, path: number[]) => (
    <div style={{ display: "grid", gap: 6, paddingLeft: path.length ? 12 : 0, borderLeft: path.length ? "1px solid var(--line)" : undefined }}>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        {(["and", "or"] as const).map((c) => <button key={c} type="button" className="btn sm ghost" aria-pressed={g.combinator === c} onClick={() => commit(update(tree, "combinator", c, path))}>{c.toUpperCase()}</button>)}
        <button type="button" className="btn sm ghost" aria-label="Add rule" onClick={() => commit(add(tree, rule(), path))}><Plus size={12} />Rule</button>
        <button type="button" className="btn sm ghost" aria-label="Add group" onClick={() => commit(add(tree, { combinator: "or", rules: [rule()] }, path))}><Plus size={12} />Group</button>
        <button type="button" className="btn sm ghost" aria-label="Add field versus field rule" onClick={() => commit(add(tree, rel("left"), path))}><Plus size={12} />Field vs field</button>
        <button type="button" className="btn sm ghost" aria-label="Add metric versus sector median rule" onClick={() => commit(add(tree, rel("metric_vs_sector"), path))}><Plus size={12} />Vs sector</button>
        {path.length ? <button type="button" className="btn sm ghost" aria-label="Remove group" onClick={() => commit(remove(tree, path))}><X size={12} /></button> : null}
      </div>
      {g.rules.map((r, i) => {
        const at = [...path, i];
        if ("rules" in r) return <div key={i}>{group(r as RuleGroupType, at)}</div>;
        const off = Boolean((r as RuleType).disabled);
        const n = r as unknown as Record<string, unknown>;
        const names = metrics.map((m) => m.name);
        const sel = (label: string, key: string, opts: string[], width: number) => <select className="input" style={{ width }} aria-label={label} value={String(n[key] ?? "")} onChange={(e) => commit(patchAt(tree, at, { [key]: e.target.value }))}>{opts.map((o) => <option key={o} value={o}>{o}</option>)}</select>;
        return (
          <div key={i} style={{ display: "flex", gap: 4, alignItems: "center", opacity: off ? 0.5 : 1 }}>
            {"left" in n ? <>{sel("Left field", "left", names, 120)}{sel("Operator", "op", REL_OPS, 64)}{sel("Right field", "right", [...names, ...names.map((m) => `${m}_sector_median`)], 170)}</> : "metric_vs_sector" in n ? <>{sel("Metric", "metric_vs_sector", names, 120)}<span className="stat-s">vs sector median ×</span>{sel("Operator", "op", REL_OPS, 64)}<input className="input num" style={{ width: 70 }} type="number" step="any" aria-label="Multiple of sector median" value={String(n.value ?? "")} onChange={(e) => commit(patchAt(tree, at, { value: e.target.value === "" ? "" : Number(e.target.value) }))} /></> : <>
            <select className="input" style={{ width: 120 }} aria-label="Field" value={r.field} onChange={(e) => commit(update(tree, "field", e.target.value, at))}>{fields.map((f) => <option key={f} value={f}>{f}</option>)}</select>
            <select className="input" style={{ width: 84 }} aria-label="Operator" value={r.operator} onChange={(e) => commit(update(tree, "operator", e.target.value, at))}>{OPERATORS.map((o) => <option key={o} value={o}>{o}</option>)}</select>
            <input className="input num" style={{ width: 90 }} aria-label="Value" value={String(r.value ?? "")} onChange={(e) => commit(update(tree, "value", e.target.value, at))} /></>}
            <input className="input num" style={{ width: 64 }} type="number" min={1} max={20} placeholder="Days" title="Held for N sessions" aria-label="Held for days" value={String(n.held_for_days ?? "")} onChange={(e) => commit(patchAt(tree, at, { held_for_days: e.target.value === "" ? undefined : Math.min(20, Math.max(1, Math.round(Number(e.target.value)))) }))} />
            <button type="button" className="btn sm ghost" aria-label={off ? "Enable rule" : "Disable rule"} onClick={() => commit(update(tree, "disabled", !off, at))}>{off ? <EyeOff size={12} /> : <Eye size={12} />}</button>
            <button type="button" className="btn sm ghost" aria-label="Remove rule" onClick={() => commit(remove(tree, at))}><X size={12} /></button>
          </div>
        );
      })}
    </div>
  );
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {group(tree, [])}
      {hasRel(tree) ? null : <input className="input num" aria-label="Formula" placeholder="pe <= 12 and (roe >= 0.15 or fcf_yield >= 0.05)" value={text ?? sql(tree)}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          if (text === null) return;
          if (!text.trim()) { commit(EMPTY); return; }
          try { commit(parseSQL(text) as RuleGroupType); } catch (e) { setError(e instanceof Error ? e.message : "Not a valid formula"); }
        }} />}
      {error ? <div className="err" role="alert">{error}</div> : null}
    </div>
  );
}
