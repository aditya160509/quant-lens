"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { ChevronDown, Info, Loader2, Repeat, RotateCcw, Save, Trash2, Upload, X } from "lucide-react";
import { MenuItem, PopMenu, Segmented, Tooltip, type MenuAt } from "@/workspace/ui";
import { uploadFile, useUniverse } from "./api";
import { label } from "./format";
import { usePresets, useSweeps } from "./store";
import type { FeatureSpec, InputSpec } from "./types";
import { UniverseBuilder } from "./UniverseBuilder";

export type FormState = Record<string, unknown>;

const UPLOAD_KIND: Record<string, string> = { signal_csv_path: "signal", event_csv_path: "event", instrument_csv_path: "instrument", factor_csv_path: "factors" };

export function defaultsFor(feature: FeatureSpec): FormState {
  return Object.fromEntries(feature.inputs.map((f) => [f.key, f.default ?? ""]));
}

/** Form state to the payload the backend expects: numbers as numbers, JSON parsed, blanks dropped. */
export function toPayload(feature: FeatureSpec, form: FormState): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of feature.inputs) {
    const v = form[f.key];
    if (v === "" || v === null || v === undefined || (Array.isArray(v) && f.type !== "multiselect" && !v.length)) continue;
    if (f.type === "number") out[f.key] = Number(v);
    else if (f.type === "json") out[f.key] = typeof v === "string" ? JSON.parse(v) : v;
    else if (f.type === "select" && f.options?.every((o) => typeof o === "number")) out[f.key] = Number(v);
    else out[f.key] = v;
  }
  return out;
}

/** Inputs a study cannot run without. The API spec has no required flag yet, so they are listed here. */
const REQUIRED: Record<string, string[]> = { "08": ["discovery_date"], "09": ["treated_unit", "treatment_date"] };

export function validate(feature: FeatureSpec, form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const f of feature.inputs) {
    const v = form[f.key];
    if (REQUIRED[feature.id]?.includes(f.key) && !form.event_csv_path && (v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length))) errors[f.key] = "Required";
    if (f.type === "json" && typeof v === "string" && v.trim()) {
      try { JSON.parse(v); } catch { errors[f.key] = "Not valid JSON"; }
    }
    if (f.type === "number" && v !== "" && v !== null && v !== undefined) {
      const n = Number(v);
      if (!Number.isFinite(n)) errors[f.key] = "Enter a number";
      else if (f.min !== undefined && n < f.min) errors[f.key] = `Minimum ${f.min}`;
      else if (f.max !== undefined && n > f.max) errors[f.key] = `Maximum ${f.max}`;
    }
  }
  return errors;
}

const isChanged = (f: InputSpec, v: unknown) => JSON.stringify(v ?? "") !== JSON.stringify(f.default ?? "");

export function StudyForm({ feature, form, setForm, errors }: {
  feature: FeatureSpec;
  form: FormState;
  setForm: (updater: (cur: FormState) => FormState) => void;
  errors: Record<string, string>;
}) {
  const hasUniverse = feature.inputs.some((f) => f.type === "ticker_list");
  const groups = useMemo(() => feature.inputs.filter((f) => !(hasUniverse && f.key === "max_symbols")).reduce<Record<string, InputSpec[]>>((acc, f) => ({ ...acc, [f.group]: [...(acc[f.group] ?? []), f] }), {}), [feature, hasUniverse]);
  const names = Object.keys(groups);
  const [open, setOpen] = useState<Record<string, boolean>>(() => Object.fromEntries(names.map((g, i) => [g, i < 2 || groups[g].some((f) => REQUIRED[feature.id]?.includes(f.key))])));
  const set = (key: string) => (value: unknown) => setForm((cur) => ({ ...cur, [key]: value }));
  const maxField = feature.inputs.find((f) => f.key === "max_symbols");

  const sweeps = useSweeps((s) => s.sweeps[feature.id]) ?? NO_SWEEP;
  const setSweep = useSweeps((s) => s.setSweep);

  return (
    <div>
      <DefaultsBar feature={feature} form={form} setForm={setForm} />
      {names.map((group) => {
        const fields = groups[group];
        const n = fields.filter((f) => isChanged(f, form[f.key])).length;
        const hasError = fields.some((f) => errors[f.key]);
        const isOpen = (open[group] ?? false) || hasError;
        return (
          <section key={group} style={{ borderBottom: "1px solid var(--line)" }}>
            <button type="button" onClick={() => setOpen((o) => ({ ...o, [group]: !isOpen }))} aria-expanded={isOpen}
              style={{ width: "100%", display: "flex", alignItems: "center", gap: 8, height: 42, padding: "0 16px", color: "var(--text)", fontSize: 13, fontWeight: 550 }}>
              {group}
              <span style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                {hasError ? <span className="dot down" /> : null}
                {n ? <span className="chip accent" style={{ height: 20 }}>{n} changed</span> : <span className="num" style={{ color: "var(--text-4)", fontSize: 11 }}>{fields.length}</span>}
                <ChevronDown size={14} style={{ transform: isOpen ? "rotate(180deg)" : "none", transition: "transform .2s var(--ease)", color: "var(--text-3)" }} />
              </span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen ? (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }} style={{ overflow: "hidden" }}>
                  <div style={{ display: "grid", gap: 16, padding: "2px 16px 18px" }}>
                    {fields.map((f) => (
                      <Field key={f.key} field={f} value={form[f.key]} error={errors[f.key]} onChange={set(f.key)} onReset={() => set(f.key)(f.default ?? "")}
                        sweep={sweeps[f.key]} onSweep={(list) => setSweep(feature.id, f.key, list)}>
                        {f.type === "ticker_list" ? (
                          <UniverseBuilder value={Array.isArray(form[f.key]) ? (form[f.key] as string[]).join(",") : String(form[f.key] ?? "")} onChange={set(f.key)}
                            maxSymbols={maxField ? Number(form.max_symbols ?? maxField.default ?? 400) : undefined} onMaxSymbols={maxField ? set("max_symbols") : undefined} />
                        ) : null}
                      </Field>
                    ))}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </section>
        );
      })}
    </div>
  );
}

const NO_SWEEP: Record<string, string> = {};

function DefaultsBar({ feature, form, setForm }: { feature: FeatureSpec; form: FormState; setForm: (u: (cur: FormState) => FormState) => void }) {
  const [at, setAt] = useState<MenuAt | null>(null);
  const presets = usePresets((s) => s.presets[feature.id]) ?? NO_PRESETS;
  const save = usePresets((s) => s.save);
  const remove = usePresets((s) => s.remove);
  const close = () => setAt(null);
  const [naming, setNaming] = useState<string | null>(null);
  const commit = () => { const name = naming?.trim(); if (name) save(feature.id, name, form); setNaming(null); };
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6, padding: "8px 12px", borderBottom: "1px solid var(--line)" }}>
      {naming !== null ? (
        <input className="input" autoFocus value={naming} placeholder="Preset name, then Enter" aria-label="Preset name" style={{ flex: 1, height: 28 }}
          onChange={(e) => setNaming(e.target.value)} onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setNaming(null); }} />
      ) : null}
      <button type="button" className="btn sm ghost" aria-haspopup="menu" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setAt({ x: r.right - 240, y: r.bottom + 4 }); }}>
        Defaults<ChevronDown size={12} />
      </button>
      <PopMenu at={at} onClose={close} width={240}>
        <MenuItem icon={<RotateCcw size={13} />} onClick={() => setForm(() => defaultsFor(feature))}>Reset to defaults</MenuItem>
        <MenuItem icon={<Save size={13} />} onClick={() => setNaming("")}>Save settings as preset…</MenuItem>
        {presets.length ? <><div className="sep" /><div className="hd">Presets</div></> : null}
        {presets.map((p) => (
          <div key={p.name} style={{ display: "flex", alignItems: "center" }}>
            <button type="button" role="menuitem" className="item" style={{ flex: 1 }} onClick={() => setForm(() => ({ ...defaultsFor(feature), ...p.values }))}>{p.name}</button>
            <button type="button" className="btn sm icon ghost" aria-label={`Delete preset ${p.name}`} onClick={(e) => { e.stopPropagation(); remove(feature.id, p.name); }}><Trash2 size={12} /></button>
          </div>
        ))}
      </PopMenu>
    </div>
  );
}
const NO_PRESETS: { name: string; values: FormState }[] = [];

function Field({ field: f, value, error, onChange, onReset, sweep, onSweep, children }: { field: InputSpec; value: unknown; error?: string; onChange: (v: unknown) => void; onReset: () => void; sweep?: string; onSweep?: (list: string | null) => void; children?: React.ReactNode }) {
  const changed = isChanged(f, value);
  if (f.type === "boolean") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ flex: 1, fontSize: 12.5, color: "var(--text-2)", fontWeight: 500 }}>{f.label}{f.help ? <HelpTip text={f.help} /> : null}</span>
        <button type="button" className="toggle" aria-pressed={Boolean(value)} aria-label={f.label} onClick={() => onChange(!value)} />
      </div>
    );
  }
  return (
    <div className="field">
      <span>
        {f.label}
        {f.help && f.type !== "ticker_list" ? <HelpTip text={f.help} /> : null}
        {f.type === "number" && onSweep ? (
          <button type="button" aria-pressed={sweep !== undefined} title="Sweep: run one job per value" onClick={() => onSweep(sweep === undefined ? String(value ?? "") : null)}
            style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: sweep !== undefined ? "var(--accent)" : "var(--text-4)" }}>
            <Repeat size={10} />sweep
          </button>
        ) : null}
        {changed ? (
          <button type="button" onClick={onReset} title="Reset to default" style={{ marginLeft: f.type === "number" ? 8 : "auto", display: "inline-flex", alignItems: "center", gap: 4, color: "var(--text-3)", fontSize: 11 }}>
            <RotateCcw size={10} />default
          </button>
        ) : null}
      </span>
      {sweep !== undefined ? <input className="input num" value={sweep} placeholder="Values, e.g. 5, 10, 20" aria-label={`${f.label} sweep values`} onChange={(e) => onSweep?.(e.target.value)} /> : children ?? <Control field={f} value={value} onChange={onChange} />}
      {error ? <span className="err">{error}</span> : null}
    </div>
  );
}

function HelpTip({ text }: { text: string }) {
  return (
    <Tooltip label={<span style={{ display: "block", maxWidth: 280, lineHeight: 1.5 }}>{text}</span>} side="left">
      <Info size={12} style={{ color: "var(--text-4)", marginLeft: 6, verticalAlign: -1, cursor: "help" }} aria-label={text} />
    </Tooltip>
  );
}

export function Control({ field: f, value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  switch (f.type) {
    case "select": {
      const opts = f.options ?? [];
      if (opts.length <= 4 && opts.every((o) => label(o).length <= 11)) {
        return <Segmented<string> label={f.label} value={String(value)} onChange={(v) => onChange(opts.find((o) => String(o) === v) ?? v)} options={opts.map((o) => ({ value: String(o), label: typeof o === "string" ? label(o) : String(o) }))} />;
      }
      if (opts.length <= 8 && opts.every((o) => label(o).length <= 18)) {
        return (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {opts.map((o) => <button key={String(o)} type="button" className="pill" aria-pressed={String(o) === String(value)} onClick={() => onChange(o)}>{typeof o === "string" ? label(o) : o}</button>)}
          </div>
        );
      }
      return (
        <select className="input" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} aria-label={f.label}>
          {opts.map((o) => <option key={String(o)} value={String(o)}>{typeof o === "string" ? label(o) : o}</option>)}
        </select>
      );
    }
    case "multiselect": {
      const sel = Array.isArray(value) ? (value as string[]) : [];
      return (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {(f.options ?? []).map((o) => {
            const on = sel.includes(String(o));
            return <button key={String(o)} type="button" className="pill" aria-pressed={on} onClick={() => onChange(on ? sel.filter((x) => x !== o) : [...sel, String(o)])}>{label(o)}</button>;
          })}
        </div>
      );
    }
    case "number": {
      const n = Number(value);
      const ranged = f.min !== undefined && f.max !== undefined && f.max - f.min > 0;
      if (ranged) {
        const fill = Number.isFinite(n) ? ((n - (f.min as number)) / ((f.max as number) - (f.min as number))) * 100 : 0;
        const step = (f.max as number) - (f.min as number) > 200 ? Math.max(1, Math.round(((f.max as number) - (f.min as number)) / 200)) : Number.isInteger(f.min) && Number.isInteger(f.max) ? 1 : 0.01;
        return (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 76px", gap: 10, alignItems: "center" }}>
            <input className="range" type="range" min={f.min} max={f.max} step={step} value={Number.isFinite(n) ? n : (f.min as number)} style={{ ["--fill" as string]: `${fill}%` }} onChange={(e) => onChange(e.target.value)} aria-label={f.label} />
            <input className="input num" style={{ height: 28, textAlign: "right" }} inputMode="decimal" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} aria-label={f.label} />
          </div>
        );
      }
      return <input className="input num" type="number" inputMode="decimal" value={String(value ?? "")} min={f.min} max={f.max} step="any" onChange={(e) => onChange(e.target.value)} />;
    }
    case "date":
      return <input className="input num" type="date" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
    case "json":
      return <textarea className="input" rows={5} spellCheck={false} value={typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""} onChange={(e) => onChange(e.target.value)} />;
    case "file":
      return <FileField kind={UPLOAD_KIND[f.key] ?? "signal"} value={String(value ?? "")} onChange={onChange} help={f.help} />;
    case "ticker":
      return <TickerPicker value={String(value ?? "")} onChange={onChange} />;
    default:
      return <input className="input" type="text" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
  }
}

function FileField({ kind, value, onChange, help }: { kind: string; value: string; onChange: (v: unknown) => void; help?: string }) {
  const [state, setState] = useState({ busy: false, error: "", info: "" });
  const [over, setOver] = useState(false);
  const pick = async (file?: File) => {
    if (!file) return;
    setState({ busy: true, error: "", info: "" });
    try {
      const res = await uploadFile(kind, file);
      onChange(res.upload_id);
      setState({ busy: false, error: "", info: `${file.name} · ${res.rows.toLocaleString()} rows` });
    } catch (err) {
      setState({ busy: false, error: err instanceof Error ? err.message : "Upload failed", info: "" });
    }
  };
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <label onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); void pick(e.dataTransfer.files?.[0]); }}
        style={{ display: "grid", placeItems: "center", gap: 4, padding: "14px 10px", borderRadius: 10, cursor: "pointer", textAlign: "center", background: over ? "var(--accent-soft)" : "var(--bg)", boxShadow: `inset 0 0 0 1px ${over ? "var(--accent-line)" : "var(--line-2)"}`, borderStyle: "dashed", color: "var(--text-2)", fontSize: 12.5 }}>
        {state.busy ? <Loader2 size={15} className="spin" /> : <Upload size={15} />}
        <span>{value ? "Replace file" : "Drop a CSV or Parquet, or click to choose"}</span>
        {help ? <span style={{ color: "var(--text-4)", fontSize: 11 }}>{help}</span> : null}
        <input type="file" accept=".csv,.parquet" hidden onChange={(e) => void pick(e.target.files?.[0])} />
      </label>
      {value ? (
        <span className="token" style={{ justifySelf: "start" }}>
          {state.info || value}
          <button type="button" aria-label="Remove file" onClick={() => { onChange(""); setState({ busy: false, error: "", info: "" }); }}><X size={10} /></button>
        </span>
      ) : null}
      {state.error ? <span className="err">{state.error}</span> : null}
    </div>
  );
}

function TickerPicker({ value, onChange }: { value: string; onChange: (v: unknown) => void }) {
  const [q, setQ] = useState("");
  const universe = useUniverse(true);
  const hits = useMemo(() => {
    const k = q.trim().toUpperCase();
    return k ? (universe.data ?? []).filter((s) => s.ticker.startsWith(k)).slice(0, 8) : [];
  }, [q, universe.data]);
  return (
    <div style={{ position: "relative" }}>
      <div className="tokens">
        {value ? <span className="token">{value}<button type="button" aria-label={`Remove ${value}`} onClick={() => onChange("")}><X size={10} /></button></span> : null}
        <input value={q} placeholder={value ? "Change" : "Search a ticker"} aria-label="Ticker" onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && q.trim()) { e.preventDefault(); onChange(hits[0]?.ticker ?? q.trim().toUpperCase()); setQ(""); } }} />
      </div>
      {hits.length ? (
        <div className="menu" role="listbox">
          {hits.map((h) => <button key={h.ticker} type="button" role="option" aria-selected={h.ticker === value} onClick={() => { onChange(h.ticker); setQ(""); }}><b>{h.ticker}</b><span>{h.sector ?? ""}</span></button>)}
        </div>
      ) : null}
    </div>
  );
}
