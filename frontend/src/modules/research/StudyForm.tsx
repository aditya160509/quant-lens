"use client";

import { DatePick } from "@/kit/DatePick";
import { FilterChips, isRangeField } from "./FilterChips";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { AnimatePresence, motion } from "framer-motion";
import { Children, createElement, useMemo, useRef, useState } from "react";
import { BookOpen, ChevronDown, Link2, Info, Loader2, Pin, Repeat, RotateCcw, Save, Trash2, Upload, X } from "lucide-react";
import { MenuItem, PopMenu, Segmented, Tooltip, type MenuAt } from "@/workspace/ui";
import { uploadFile, useUniverse, type UploadInfo } from "./api";
import { label } from "./format";
import { lab } from "./lab";
import { usePresets, useSweeps } from "./store";
import { useUniverses } from "./api";
import type { FeatureSpec, InputSpec } from "./types";
import { UniverseBuilder } from "./UniverseBuilder";

export type FormState = Record<string, unknown>;

const UPLOAD_KIND: Record<string, string | string[]> = {
  signal_csv_path: "signal", event_csv_path: "event", instrument_csv_path: "instrument", factor_csv_path: "factors",
  upload_id: ["predictions", "returns", "feature_panel", "trial_matrix"], trials_upload_id: "trial_matrix", benchmark_upload_id: "returns",
};

/** What each bring-your-own-data upload holds, with a template a user can download and fill. */
const UPLOAD_FORMAT: Record<string, { label: string; about: string; template: string }> = {
  predictions: { label: "Predictions", about: "One row per date and ticker: your model's score and, ideally, the realised outcome.", template: "date,ticker,prediction,outcome\n2024-01-02,AAPL,0.42,0.0031\n2024-01-02,MSFT,-0.10,-0.0012\n" },
  returns: { label: "Returns", about: "One row per date: your strategy's period return as a decimal (0.01 = 1%).", template: "date,return\n2024-01-02,0.0042\n2024-01-03,-0.0017\n" },
  feature_panel: { label: "Feature panel", about: "One row per date and ticker: your own features and the forward outcome to predict.", template: "date,ticker,f1,f2,outcome\n2024-01-02,AAPL,0.8,-1.2,0.0031\n2024-01-02,MSFT,0.1,0.4,-0.0012\n" },
  trial_matrix: { label: "Trial matrix", about: "One column per configuration you tried, so overfitting tests use the true trial count.", template: "date,trial_1,trial_2,trial_3\n2024-01-02,0.004,0.001,-0.002\n2024-01-03,-0.001,0.003,0.000\n" },
};

/** Settings a reader made their own default for a study, kept on this device; they replace the built-in defaults. */
export const useUserDefaults = create<{ defaults: Record<string, FormState>; set: (id: string, form: FormState | null) => void }>()(
  persist((set) => ({ defaults: {}, set: (id, form) => set((s) => { const d = { ...s.defaults }; if (form) d[id] = form; else delete d[id]; return { defaults: d }; }) }),
    { name: "research-user-defaults", storage: createJSONStorage(() => localStorage), version: 1 }),
);

export const factoryDefaults = (feature: FeatureSpec): FormState => Object.fromEntries(feature.inputs.map((f) => [f.key, f.default ?? ""]));

export function defaultsFor(feature: FeatureSpec): FormState {
  return { ...factoryDefaults(feature), ...useUserDefaults.getState().defaults[feature.id] };
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
  // Universe-wide filters from MarketFilters are not per-feature inputs; pass them through when set.
  for (const k of ["regions", "asset_types", "min_price", "min_dollar_volume", "min_listing_months"]) {
    const v = form[k];
    if (v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length) && !(k in out)) out[k] = v;
  }
  return out;
}

/** Inputs a study cannot run without. The API spec has no required flag yet, so they are listed here. */
const REQUIRED: Record<string, string[]> = { "08": ["discovery_date"], "09": ["treated_unit", "treatment_date"] };

/** A field shows when the API's depends_on rule (if any) matches the current form. */
export const applies = (f: InputSpec, form: FormState) => {
  const d = f.depends_on;
  if (!d) return true;
  const v = form[d.field];
  if (d.present) return v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length);
  return (d.values ?? []).map(String).includes(String(v ?? ""));
};

const LEVELS = ["quick", "standard", "expert"] as const;
type Level = (typeof LEVELS)[number];
const levelOf = (f: InputSpec): Level => f.level ?? "standard";

export function validate(feature: FeatureSpec, form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const f of feature.inputs) {
    const v = form[f.key];
    if (!applies(f, form)) continue;
    if ((f.required || REQUIRED[feature.id]?.includes(f.key)) && !form.event_csv_path && (v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length))) errors[f.key] = "Required";
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
  if (feature.id === "mlvalidate" && feature.inputs.some((f) => f.key === "upload_id") && !form.upload_id && !form.artifact_id && !form.source_result) errors.upload_id = "Upload data or choose an Alpha or Allocation run.";
  return errors;
}

const isChanged = (f: InputSpec, v: unknown) => JSON.stringify(v ?? "") !== JSON.stringify(f.default ?? "");

export function StudyForm({ feature, form, setForm, errors: submittedErrors }: {
  feature: FeatureSpec;
  form: FormState;
  setForm: (updater: (cur: FormState) => FormState) => void;
  errors: Record<string, string>;
}) {
  const liveErrors = validate(feature, form);
  // Show invalid edited values immediately; required defaults wait until submission.
  const errors = Object.fromEntries(Object.entries(liveErrors).filter(([key]) => submittedErrors[key] || isChanged(feature.inputs.find((f) => f.key === key)!, form[key])));
  const hasUniverse = feature.inputs.some((f) => f.type === "ticker_list");
  const level = useFormLevel((st) => st.level);
  const setLevel = useFormLevel((st) => st.set);
  const hasLevels = feature.inputs.some((f) => f.level);
  const shownLevels = LEVELS.slice(0, LEVELS.indexOf(level) + 1);
  const groups = useMemo(() => feature.inputs.filter((f) => !(hasUniverse && f.key === "max_symbols") && (!hasLevels || shownLevels.includes(levelOf(f)) || (form[f.key] !== undefined && isChanged(f, form[f.key]))) && applies(f, form)).reduce<Record<string, InputSpec[]>>((acc, f) => ({ ...acc, [f.group]: [...(acc[f.group] ?? []), f] }), {}), [feature, hasUniverse, hasLevels, shownLevels, form]);
  const names = Object.keys(groups);
  const [open, setOpen] = useState<Record<string, boolean>>(() => Object.fromEntries(names.map((g, i) => [g, i < 2 || groups[g].some((f) => REQUIRED[feature.id]?.includes(f.key))])));
  const set = (key: string) => (value: unknown) => setForm((cur) => ({ ...cur, [key]: value }));
  const maxField = feature.inputs.find((f) => f.key === "max_symbols");

  const sweeps = useSweeps((s) => s.sweeps[feature.id]) ?? NO_SWEEP;
  const setSweep = useSweeps((s) => s.setSweep);

  return (
    <div>
      <DefaultsBar feature={feature} form={form} setForm={setForm} />
      {hasLevels ? (
        <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)" }}>
          <Segmented<Level> label="How many settings to show" value={level} onChange={setLevel} options={[{ value: "quick", label: "Quick" }, { value: "standard", label: "Standard" }, { value: "expert", label: "Expert" }]} />
        </div>
      ) : null}
      <Conflicts feature={feature} form={form} />
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
                    {(group === "Filters" ? fields.filter((f) => !isRangeField(f)) : fields).map((f) => (
                      <Field key={f.key} field={f} value={form[f.key]} error={errors[f.key]} onChange={set(f.key)} onReset={() => set(f.key)(f.default ?? "")}
                        sweep={sweeps[f.key]} onSweep={(list) => setSweep(feature.id, f.key, list)}>
                        {f.type === "ticker_list" ? (
                          <UniverseBuilder value={Array.isArray(form[f.key]) ? (form[f.key] as string[]).join(",") : String(form[f.key] ?? "").toLowerCase() === "master" ? "" : String(form[f.key] ?? "")} onChange={set(f.key)}
                            maxSymbols={maxField ? Number(form.max_symbols ?? maxField.default ?? 400) : undefined} onMaxSymbols={maxField ? set("max_symbols") : undefined} />
                        ) : null}
                        {lab().widgets?.[f.key] ? createElement(lab().widgets![f.key], { field: f, value: form[f.key], onChange: set(f.key) }) : null}
                        {f.type === "ticker_list" && f.key === "universe" ? (
                          <MarketFilters form={form} set={(k, v) => setForm((cur) => ({ ...cur, [k]: v }))} />
                        ) : null}
                      </Field>
                    ))}
                    {group === "Filters" ? <FilterChips scope={feature.id} fields={fields.filter(isRangeField)} form={form} setForm={setForm} /> : null}
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
  const userSet = useUserDefaults((st) => Boolean(st.defaults[feature.id]));
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
        <MenuItem icon={<Pin size={13} />} onClick={() => { useUserDefaults.getState().set(feature.id, form); close(); }}>Make these my defaults</MenuItem>
        <MenuItem icon={<RotateCcw size={13} />} onClick={() => setForm(() => defaultsFor(feature))}>Reset to {userSet ? "my defaults" : "defaults"}</MenuItem>
        {userSet ? <MenuItem icon={<RotateCcw size={13} />} onClick={() => { useUserDefaults.getState().set(feature.id, null); setForm(() => factoryDefaults(feature)); }}>Reset to built-in defaults</MenuItem> : null}
        <MenuItem icon={<Link2 size={13} />} onClick={() => { const u = new URL(location.href); u.searchParams.set("s", encodeSettings(form)); u.searchParams.delete("run"); void navigator.clipboard?.writeText(u.toString()); }}>Copy link with these settings</MenuItem>
        <div className="sep" /><div className="hd">From the literature</div>
        {LIT_PRESETS.filter((p) => Object.keys(p.values).some((k) => feature.inputs.some((f) => f.key === k))).map((p) => (
          <MenuItem key={p.name} icon={<BookOpen size={13} />} onClick={() => setForm((cur) => ({ ...cur, ...Object.fromEntries(Object.entries(p.values).filter(([k, v]) => { const f = feature.inputs.find((x) => x.key === k); return f && (!f.options || f.options.map(String).includes(String(v)) || Array.isArray(v)); })) }))}>
            <span style={{ display: "grid" }}><span>{p.name}</span><span style={{ fontSize: 11, color: "var(--text-4)" }}>{p.note}</span></span>
          </MenuItem>
        ))}
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
        {f.label}{f.unit ? <span style={{ color: "var(--text-4)", fontWeight: 400 }}> ({f.unit})</span> : null}
        {(f.help || f.citation) && f.type !== "ticker_list" ? <HelpTip text={[f.help, f.citation ? `Default follows ${f.citation}.` : ""].filter(Boolean).join(" ")} /> : null}
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
      {sweep !== undefined ? <input className="input num" value={sweep} placeholder="Values, e.g. 5, 10, 20" aria-label={`${f.label} sweep values`} onChange={(e) => onSweep?.(e.target.value)} /> : (Children.toArray(children).length ? children : null) ?? (f.key === "lookback_days" ? <WindowBrush field={f} value={Number(value ?? f.default ?? 3650)} onChange={onChange} /> : <Control field={f} value={value} onChange={onChange} />)}
      {error ? <span className="err" role="alert">{error}</span> : null}
    </div>
  );
}

function HelpTip({ text }: { text: string }) {
  return (
    <Tooltip label={<span style={{ display: "block", maxWidth: 280, lineHeight: 1.5 }}>{text}</span>} side="left">
      <button type="button" className="btn sm icon ghost" aria-label={`Explain this setting: ${text}`} style={{ display: "inline-flex", marginLeft: 4, verticalAlign: "middle" }}><Info size={12} aria-hidden /></button>
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
      return <input className="input num" type="number" inputMode="decimal" value={String(value ?? "")} min={f.min} max={f.max} step="any" aria-label={f.label} onChange={(e) => onChange(e.target.value)} />;
    }
    case "date":
      return <DatePick label={f.label} value={String(value ?? "")} onChange={onChange} />;
    case "json":
      return <textarea className="input" rows={5} aria-label={f.label} spellCheck={false} value={typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""} onChange={(e) => onChange(e.target.value)} />;
    case "file":
      return <FileField kind={UPLOAD_KIND[f.key] ?? "signal"} value={String(value ?? "")} onChange={onChange} help={f.help} />;
    case "ticker":
      return <TickerPicker value={String(value ?? "")} onChange={onChange} />;
    default:
      return <input className="input" type="text" aria-label={f.label} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
  }
}

function FileField({ kind, value, onChange, help }: { kind: string | string[]; value: string; onChange: (v: unknown) => void; help?: string }) {
  const kinds = Array.isArray(kind) ? kind : [kind];
  const [chosen, setChosen] = useState(kinds[0]);
  const [state, setState] = useState<{ busy: boolean; error: string; name: string; info: UploadInfo | null }>({ busy: false, error: "", name: "", info: null });
  const [over, setOver] = useState(false);
  const fmt = UPLOAD_FORMAT[chosen];
  const pick = async (file?: File) => {
    if (!file) return;
    setState({ busy: true, error: "", name: file.name, info: null });
    try {
      const res = await uploadFile(chosen, file);
      onChange(res.upload_id);
      setState({ busy: false, error: "", name: file.name, info: res });
    } catch (err) {
      setState({ busy: false, error: err instanceof Error ? err.message : "Upload failed", name: file.name, info: null });
    }
  };
  const template = () => {
    if (!fmt) return;
    const url = URL.createObjectURL(new Blob([fmt.template], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${chosen}_template.csv` });
    a.click();
    URL.revokeObjectURL(url);
  };
  const info = state.info;
  return (
    <div className="upload">
      {kinds.length > 1 ? (
        <div className="upload-kinds" role="group" aria-label="What you are uploading">
          {kinds.map((k) => (
            <button key={k} type="button" className="pill" aria-pressed={k === chosen}
              onClick={() => { setChosen(k); if (value) onChange(""); setState({ busy: false, error: "", name: "", info: null }); }}>{UPLOAD_FORMAT[k]?.label ?? label(k)}</button>
          ))}
        </div>
      ) : null}
      {fmt ? <p className="upload-about">{fmt.about} <button type="button" className="link" onClick={template}>Download a template</button></p> : null}
      <label className="upload-drop" data-over={over || undefined} data-busy={state.busy || undefined} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); void pick(e.dataTransfer.files?.[0]); }}>
        {state.busy ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
        <span>{state.busy ? `Checking ${state.name}…` : value ? "Replace file" : "Drop a CSV here, or click to choose"}</span>
        <span className="upload-hint">{help && !fmt ? help : "CSV only, up to 10 MB. Checked for future dates, duplicates and formula cells; kept privately for 24 hours."}</span>
        <input type="file" accept=".csv,text/csv" hidden onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      {value ? (
        <div className="upload-receipt">
          <div className="upload-receipt-h">
            <b>{state.name || "Uploaded file"}</b>
            <button type="button" aria-label="Remove file" onClick={() => { onChange(""); setState({ busy: false, error: "", name: "", info: null }); }}><X size={11} /></button>
          </div>
          {info ? (
            <dl>
              <div><dt>Rows</dt><dd className="num">{info.rows.toLocaleString()}</dd></div>
              {info.date_range ? <div><dt>Dates</dt><dd className="num">{info.date_range[0]} → {info.date_range[1]}</dd></div> : null}
              <div><dt>Columns</dt><dd>{info.columns.join(", ")}</dd></div>
              {info.nan_share && Object.values(info.nan_share).some((x) => x > 0) ? <div><dt>Missing</dt><dd className="num">{Object.entries(info.nan_share).filter(([, x]) => x > 0).map(([k, x]) => `${k} ${(x * 100).toFixed(1)}%`).join(" · ")}</dd></div> : null}
            </dl>
          ) : null}
          {info?.warnings?.length ? <ul className="upload-warn">{info.warnings.map((w) => <li key={w}>{w}</li>)}</ul> : null}
        </div>
      ) : null}
      {state.error ? <span className="err" role="alert">{state.error}</span> : null}
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

/** Quick / Standard / Expert, remembered across features. */
const useFormLevel = create<{ level: Level; set: (l: Level) => void }>()(persist((set) => ({ level: "standard", set: (level) => set({ level }) }), { name: "research-form-level", storage: createJSONStorage(() => localStorage) }));

/** Settings the API says cannot be combined, shown before the run instead of as a backend error. */
function Conflicts({ feature, form }: { feature: FeatureSpec; form: FormState }) {
  const hits = feature.inputs.flatMap((f) => (f.conflicts_with ?? []).filter((o) => isSet(form[f.key]) && isSet(form[o])).map((o) => [f.label, feature.inputs.find((x) => x.key === o)?.label ?? o] as const));
  const unique = [...new Map(hits.map(([a, b]) => [[a, b].sort().join("|"), [a, b] as const])).values()];
  if (!unique.length) return null;
  return (
    <div style={{ margin: 10, padding: "8px 10px", borderRadius: 9, background: "var(--warn-soft)", fontSize: 12, color: "var(--text-2)" }}>
      {unique.map(([a, b]) => <div key={a + b}><b>{a}</b> and <b>{b}</b> cannot both be set; the study will use {a}.</div>)}
    </div>
  );
}
const isSet = (v: unknown) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length) && v !== false;

/** Settings that follow well-known papers; only keys this feature has are applied. */
const LIT_PRESETS: { name: string; note: string; values: Record<string, unknown> }[] = [
  { name: "Fama & French (1993)", note: "NYSE breakpoints, value-weighted, ex-financials", values: { breakpoints: "nyse", weighting: "value", universe_filters: ["ex_financials"], n_portfolios: 10 } },
  { name: "Novy-Marx & Velikov (2023)", note: "Quintiles, VW and EW, microcaps excluded, costs on", values: { n_portfolios: 5, weighting: "value", universe_filters: ["ex_microcaps"], breakpoints: "nyse", include_costs: true } },
  { name: "Jegadeesh & Titman (1993)", note: "12-1 momentum, deciles, equal-weighted", values: { signal: "momentum", n_portfolios: 10, weighting: "equal", formation_months: 12, skip_months: 1 } },
  { name: "Hou, Xue & Zhang (2020)", note: "NYSE breakpoints, VW, microcaps excluded", values: { breakpoints: "nyse", weighting: "value", universe_filters: ["ex_microcaps"] } },
  { name: "Harvey, Liu & Zhu (2016)", note: "t-hurdle 3.0, BHY correction", values: { t_threshold: 3, threshold_rule: "hlz_bhy", multiple_testing: "bhy" } },
];

export const encodeSettings = (form: FormState) => btoa(unescape(encodeURIComponent(JSON.stringify(form)))).replace(/=+$/, "");
export const decodeSettings = (s: string): FormState | null => { try { return JSON.parse(decodeURIComponent(escape(atob(s)))) as FormState; } catch { return null; } };

/**
 * Every market and asset type in the data, with liquidity floors. Writes `regions`, `asset_types`,
 * `min_price`, `min_dollar_volume` and `min_listing_months` into the payload (contract §3).
 */
function MarketFilters({ form, set }: { form: FormState; set: (k: string, v: unknown) => void }) {
  const uni = useUniverses();
  const [open, setOpen] = useState(false);
  // Country × asset-type rows only; the aggregate rows ("global", regions) would double count.
  const rows = (uni.data ?? []).filter((u) => u.id.includes("."));
  if (uni.isError || !rows.length) return null;
  const regions = [...new Map(rows.map((u) => [u.region, 0])).keys()];
  const types = [...new Map(rows.map((u) => [u.asset_type, 0])).keys()];
  const sel = (k: string) => (Array.isArray(form[k]) ? (form[k] as string[]) : []);
  const toggle = (k: string, v: string) => { const cur = sel(k); set(k, cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]); };
  const pickedRegions = sel("regions"), pickedTypes = sel("asset_types");
  const count = rows.filter((u) => (!pickedRegions.length || pickedRegions.includes(u.region)) && (!pickedTypes.length || pickedTypes.includes(u.asset_type))).reduce((a, u) => a + u.count, 0);
  const total = rows.reduce((a, u) => a + u.count, 0);
  return (
    <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
      <button type="button" className="btn sm ghost" style={{ justifySelf: "start" }} onClick={() => setOpen((v) => !v)}>
        Markets &amp; liquidity · <b className="num">{count.toLocaleString()}</b>&nbsp;of {total.toLocaleString()} instruments <ChevronDown size={12} />
      </button>
      {open ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div className="xpills">{regions.map((r) => <button key={r} type="button" className="pill" aria-pressed={pickedRegions.includes(r)} onClick={() => toggle("regions", r)}>{label(r)}</button>)}</div>
          <div className="xpills">{types.map((t) => <button key={t} type="button" className="pill" aria-pressed={pickedTypes.includes(t)} onClick={() => toggle("asset_types", t)}>{label(t)}</button>)}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
            <label className="xc"><span>Min price ($)</span><input className="input num" inputMode="decimal" value={String(form.min_price ?? "")} placeholder="1" onChange={(e) => set("min_price", e.target.value === "" ? undefined : Number(e.target.value))} /></label>
            <label className="xc"><span>Min $ volume (M)</span><input className="input num" inputMode="decimal" value={form.min_dollar_volume ? String(Number(form.min_dollar_volume) / 1e6) : ""} placeholder="0" onChange={(e) => set("min_dollar_volume", e.target.value === "" ? undefined : Number(e.target.value) * 1e6)} /></label>
            <label className="xc"><span>Listed for (months)</span><input className="input num" inputMode="numeric" value={String(form.min_listing_months ?? "")} placeholder="12" onChange={(e) => set("min_listing_months", e.target.value === "" ? undefined : Number(e.target.value))} /></label>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Market episodes drawn on the window timeline, so a chosen window shows what it includes. */
const EPISODES: { from: string; to: string; label: string }[] = [
  { from: "2007-10", to: "2009-03", label: "GFC" },
  { from: "2011-07", to: "2011-10", label: "Euro crisis" },
  { from: "2015-08", to: "2016-02", label: "China / oil" },
  { from: "2020-02", to: "2020-04", label: "COVID" },
  { from: "2022-01", to: "2022-10", label: "Rate shock" },
];

/**
 * The sample window as a timeline: drag the start edge (the window always ends at the latest data),
 * with crises shaded and preset lengths. Writes lookback_days.
 */
function WindowBrush({ field: f, value, onChange }: { field: InputSpec; value: number; onChange: (v: unknown) => void }) {
  // The window ends at the latest data, i.e. now; read once per mount, not on every render.
  const [end] = useState(() => Date.now());
  const maxDays = f.max ?? 11000, minDays = f.min ?? 365;
  const t0 = end - maxDays * 864e5;
  const x = (t: number) => Math.max(0, Math.min(100, ((t - t0) / (end - t0)) * 100));
  const startPct = x(end - value * 864e5);
  const track = useRef<HTMLDivElement>(null);
  const drag = (clientX: number) => {
    const r = track.current?.getBoundingClientRect();
    if (!r) return;
    const pct = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
    const days = Math.round(((end - (t0 + pct * (end - t0))) / 864e5) / 30) * 30;
    onChange(Math.max(minDays, Math.min(maxDays, days)));
  };
  const years = (value / 365.25).toFixed(1).replace(/\.0$/, "");
  const startYear = new Date(end - value * 864e5).getFullYear();
  const ticks = Array.from({ length: 7 }, (_, i) => t0 + (i / 6) * (end - t0));
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div ref={track} className="wb-track" role="slider" aria-label={f.label} aria-valuemin={minDays} aria-valuemax={maxDays} aria-valuenow={value} tabIndex={0}
        onPointerDown={(e) => { (e.target as HTMLElement).setPointerCapture?.(e.pointerId); drag(e.clientX); }}
        onPointerMove={(e) => { if (e.buttons) drag(e.clientX); }}
        onKeyDown={(e) => { if (e.key === "ArrowLeft") onChange(Math.min(maxDays, value + 365)); if (e.key === "ArrowRight") onChange(Math.max(minDays, value - 365)); }}>
        {EPISODES.map((ep) => {
          const a = x(Date.parse(ep.from + "-01")), b = x(Date.parse(ep.to + "-28"));
          return b > 0 ? <span key={ep.label} className="wb-ep" style={{ left: `${a}%`, width: `${Math.max(0.6, b - a)}%` }} title={ep.label} /> : null;
        })}
        <span className="wb-sel" style={{ left: `${startPct}%`, right: 0 }} />
        <span className="wb-handle" style={{ left: `${startPct}%` }} />
      </div>
      <div className="wb-ticks">{ticks.map((t, i) => <span key={i}>{new Date(t).getFullYear()}</span>)}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span className="num" style={{ fontSize: 12, color: "var(--text-2)" }}>{startYear} → latest · {years} years</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          {[3, 5, 7, 10, 15, 20].filter((y) => y * 365 <= maxDays && y * 365 >= minDays).map((y) => (
            <button key={y} type="button" className="pill" style={{ height: 22, fontSize: 11 }} aria-pressed={Math.abs(value - y * 365) < 40} onClick={() => onChange(y * 365)}>{y}y</button>
          ))}
        </span>
      </div>
    </div>
  );
}
