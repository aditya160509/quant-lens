"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Upload, X } from "lucide-react";
import { searchSymbols, uploadFile } from "./api";
import { title } from "./format";

const UPLOAD_KIND = { signal_csv_path: "signal", event_csv_path: "event", instrument_csv_path: "instrument", factor_csv_path: "factors" };
const NAMED_UNIVERSES = ["us_equities"];

export function defaultsFor(feature) {
  return Object.fromEntries(feature.inputs.map((f) => [f.key, f.default ?? ""]));
}

/** Convert form state to the payload the backend expects (numbers as numbers, JSON parsed, blanks dropped). */
export function toPayload(feature, form) {
  const out = {};
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

export function validate(feature, form) {
  const errors = {};
  for (const f of feature.inputs) {
    const v = form[f.key];
    if (f.type === "json" && v) { try { JSON.parse(v); } catch { errors[f.key] = "Not valid JSON"; } }
    if (f.type === "number" && v !== "" && v !== null && v !== undefined) {
      const n = Number(v);
      if (!Number.isFinite(n)) errors[f.key] = "Enter a number";
      else if (f.min !== undefined && n < f.min) errors[f.key] = `Minimum ${f.min}`;
      else if (f.max !== undefined && n > f.max) errors[f.key] = `Maximum ${f.max}`;
    }
  }
  return errors;
}

export function StudyForm({ feature, form, setForm, errors }) {
  const groups = useMemo(() => feature.inputs.reduce((acc, f) => ({ ...acc, [f.group]: [...(acc[f.group] ?? []), f] }), {}), [feature]);
  const set = (key) => (value) => setForm((cur) => ({ ...cur, [key]: value }));
  return <div className="rv2-form">{Object.entries(groups).map(([group, fields]) => <fieldset key={group}><legend>{group}</legend><div>
    {fields.map((f) => <label key={f.key} className={`rv2-field ${["json", "multiselect", "ticker_list"].includes(f.type) ? "wide" : ""}`}>
      <span>{f.label}{f.help ? <i title={f.help}>?</i> : null}</span>
      <Control field={f} value={form[f.key]} onChange={set(f.key)} />
      {errors?.[f.key] ? <em className="rv2-error">{errors[f.key]}</em> : f.help && ["file", "json", "ticker_list"].includes(f.type) ? <small>{f.help}</small> : null}
    </label>)}
  </div></fieldset>)}</div>;
}

function Control({ field: f, value, onChange }) {
  switch (f.type) {
    case "select":
      return (f.options?.length ?? 0) <= 6
        ? <div className="rv2-chips">{f.options.map((o) => <button type="button" key={String(o)} className={String(o) === String(value) ? "on" : ""} onClick={() => onChange(o)}>{typeof o === "string" ? title(o) : o}</button>)}</div>
        : <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>{f.options.map((o) => <option key={String(o)} value={String(o)}>{typeof o === "string" ? title(o) : o}</option>)}</select>;
    case "multiselect": {
      const sel = Array.isArray(value) ? value : [];
      return <div className="rv2-chips">{f.options.map((o) => <button type="button" key={o} className={sel.includes(o) ? "on" : ""} onClick={() => onChange(sel.includes(o) ? sel.filter((x) => x !== o) : [...sel, o])}>{title(o)}</button>)}</div>;
    }
    case "boolean":
      return <button type="button" className={`rv2-toggle ${value ? "on" : ""}`} onClick={() => onChange(!value)} aria-pressed={Boolean(value)}><i /></button>;
    case "number":
      return <input type="number" value={value ?? ""} min={f.min} max={f.max} step="any" onChange={(e) => onChange(e.target.value)} />;
    case "date":
      return <input type="date" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
    case "json":
      return <textarea value={typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""} onChange={(e) => onChange(e.target.value)} spellCheck={false} rows={4} />;
    case "file":
      return <FileField kind={UPLOAD_KIND[f.key] ?? "signal"} value={value} onChange={onChange} />;
    case "ticker":
      return <TickerField value={value} onChange={onChange} single />;
    case "ticker_list":
      return <TickerField value={value} onChange={onChange} />;
    default:
      return <input type="text" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

function FileField({ kind, value, onChange }) {
  const [state, setState] = useState({ busy: false, error: "", info: "" });
  const pick = async (file) => {
    if (!file) return;
    setState({ busy: true, error: "", info: "" });
    try {
      const res = await uploadFile(kind, file);
      onChange(res.upload_id);
      setState({ busy: false, error: "", info: `${file.name}: ${res.rows.toLocaleString()} rows` });
    } catch (err) {
      setState({ busy: false, error: err.message, info: "" });
    }
  };
  return <div className="rv2-file">
    <label className="rv2-file-btn">{state.busy ? <Loader2 size={13} className="spin" /> : <Upload size={13} />}{value ? "Replace" : "Upload CSV / Parquet"}<input type="file" accept=".csv,.parquet" onChange={(e) => pick(e.target.files?.[0])} hidden /></label>
    {value ? <span className="rv2-token">{state.info || value}<button type="button" onClick={() => { onChange(""); setState({ busy: false, error: "", info: "" }); }} aria-label="Remove upload"><X size={11} /></button></span> : null}
    {state.error ? <em className="rv2-error">{state.error}</em> : null}
  </div>;
}

function TickerField({ value, onChange, single = false }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const tokens = String(value ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  useEffect(() => {
    if (!q) return undefined;
    const id = setTimeout(() => searchSymbols(q).then(setHits).catch(() => setHits([])), 180);
    return () => clearTimeout(id);
  }, [q]);
  const shown = q ? hits : [];
  const add = (t) => { onChange(single ? t : [...tokens.filter((x) => !NAMED_UNIVERSES.includes(x)), t].join(",")); setQ(""); setHits([]); };
  return <div className="rv2-ticker">
    <div className="rv2-ticker-box">
      {tokens.map((t) => <span key={t} className="rv2-token">{t}<button type="button" onClick={() => onChange(tokens.filter((x) => x !== t).join(","))} aria-label={`Remove ${t}`}><X size={11} /></button></span>)}
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={tokens.length ? "Add ticker" : single ? "Search ticker" : "us_equities, or search tickers"} onKeyDown={(e) => { if (e.key === "Enter" && q.trim()) { e.preventDefault(); add(q.trim().toUpperCase()); } }} />
      {!single && !tokens.includes("us_equities") ? <button type="button" className="rv2-link" onClick={() => onChange("us_equities")}>US equities</button> : null}
    </div>
    {shown.length ? <div className="rv2-ticker-menu">{shown.map((h) => <button type="button" key={h.ticker} onClick={() => add(h.ticker)}><b>{h.ticker}</b><span>{h.sector ?? ""}</span></button>)}</div> : null}
  </div>;
}
