"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { num } from "@/modules/research/format";
import { send } from "../api";
import { FormulaBar } from "./FormulaBar";

type Catalogue = { fields: string[]; functions: string[]; metrics: { name: string; expression: string; show: boolean }[] };
type Preview = { names: number; of: number; known: number; min: number | null; median: number | null; max: number | null; top: { ticker: string; value: number }[] };

/** The formula field: highlighted, completes fields and functions, shows what the formula gives today, and saves named metrics. */
export function FormulaControl({ value: raw, onChange }: { value: unknown; onChange: (v: unknown) => void }) {
  const value = String(raw ?? "");
  const qc = useQueryClient();
  const catalogue = useQuery({ queryKey: ["screener", "catalogue"], queryFn: () => send<Catalogue>("GET", "/formula/catalogue"), staleTime: Infinity });
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setSettled(value), 400);
    return () => clearTimeout(id);
  }, [value]);
  const preview = useQuery({ queryKey: ["screener", "preview", settled], queryFn: () => send<Preview>("POST", "/formula/preview", { payload: { formula: settled } }), enabled: settled.trim().length > 0, retry: false });
  const metrics = useMemo(() => catalogue.data?.metrics ?? [], [catalogue.data]);
  const fields = useMemo(() => [...(catalogue.data?.fields ?? []), ...metrics.map((m) => m.name)], [catalogue.data, metrics]);
  const functions = useMemo(() => catalogue.data?.functions ?? [], [catalogue.data]);
  const [name, setName] = useState("");
  const [show, setShow] = useState(true);
  const refresh = () => qc.invalidateQueries({ queryKey: ["screener", "catalogue"] });
  const save = useMutation({ mutationFn: () => send("PUT", `/metrics/${name}`, { expression: value, show }), onSuccess: () => { setName(""); void refresh(); } });
  const remove = useMutation({ mutationFn: (n: string) => send("DELETE", `/metrics/${n}`), onSuccess: () => void refresh() });
  const p = preview.data;
  const summary = p
    ? `${p.known.toLocaleString()} of ${p.names.toLocaleString()}${p.names < p.of ? ` largest of ${p.of.toLocaleString()}` : ""} names known · min ${num(p.min, 3)} · median ${num(p.median, 3)} · max ${num(p.max, 3)} · top ${p.top.map((t) => `${t.ticker} ${num(t.value, 3)}`).join(", ") || "none"}`
    : preview.isFetching ? "Evaluating" : null;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <FormulaBar value={value} onChange={onChange} fields={fields} functions={functions} error={preview.error?.message} preview={summary} />
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <input className="input" style={{ width: 150 }} placeholder="metric_name" aria-label="Metric name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" className="pill" aria-pressed={show} onClick={() => setShow(!show)}>Column</button>
        <button type="button" className="btn sm" disabled={!name || !value.trim() || save.isPending} onClick={() => save.mutate()}>Save metric</button>
        {save.error ? <span role="alert" style={{ color: "var(--down)", fontSize: 12 }}>{save.error.message}</span> : null}
      </div>
      {metrics.length ? (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {metrics.map((m) => (
            <span key={m.name} className="pill" title={m.expression} style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
              <button type="button" onClick={() => onChange(m.expression)}>{m.name}{m.show ? " · column" : ""}</button>
              <button type="button" aria-label={`Delete ${m.name}`} onClick={() => remove.mutate(m.name)}><X size={10} /></button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
