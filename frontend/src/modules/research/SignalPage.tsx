"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BookOpen, Check, ClipboardCheck, FlaskConical, Layers, Save, Search, Sparkles, X } from "lucide-react";
import { Bars } from "@/charts/Bars";
import { Chip, Segmented } from "@/workspace/ui";
import { combineExprs, saveSignal, useActiveSignal, useFields, useLibrary, useLiterature, useOperators, useSavedSignal, useSavedSignals, validateExpr, type LibrarySignal, type Validation } from "./api";
import { label } from "./format";

/**
 * The Signal page: write a formula (or load one), see what it looks like before running anything,
 * then make it the signal every test on the other pages uses.
 */
export function SignalPage() {
  const active = useActiveSignal();
  const [expr, setExpr] = useState(active.expr ?? "rank(delay(close, 1) / delay(close, 12) - 1)");
  const [name, setName] = useState(active.name ?? "My signal");
  const [check, setCheck] = useState<Validation | null>(null);
  const [checking, setChecking] = useState(false);
  const [tab, setTab] = useState<"library" | "saved" | "combine" | "reference">("library");
  const ops = useOperators();
  const fields = useFields();
  const offline = ops.isError && fields.isError;

  // Validate as the formula settles; a stale answer never overwrites a newer one.
  const seq = useRef(0);
  useEffect(() => {
    const id = ++seq.current;
    const t = setTimeout(() => {
      if (!expr.trim()) { setCheck(null); return; }
      setChecking(true);
      validateExpr(expr).then((v) => { if (id === seq.current) setCheck(v); }).catch(() => { if (id === seq.current) setCheck(null); }).finally(() => { if (id === seq.current) setChecking(false); });
    }, 450);
    return () => clearTimeout(t);
  }, [expr]);

  const isActive = active.expr === expr;
  const use = () => active.set({ expr, name });

  return (
    <div className="island" style={{ overflowY: "auto" }}>
      <div style={{ padding: "22px 22px 30px", maxWidth: 1320 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 16 }}>
          <div className="ov-icon" style={{ width: 40, height: 40, borderRadius: 11 }}><FlaskConical size={19} strokeWidth={1.6} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em" }}>Signal</h1>
            <p style={{ marginTop: 4, color: "var(--text-2)", fontSize: 13.5 }}>Write the signal as a formula, load a published anomaly, or combine several. Every test then runs on it.</p>
          </div>
          {active.expr ? <Chip tone="accent">Testing: {active.name ?? "formula"}</Chip> : <Chip>Using each page&apos;s built-in signal</Chip>}
        </div>

        {offline ? (
          <div className="card" style={{ height: "auto", marginBottom: 12 }}><div className="card-b" style={{ color: "var(--text-3)", fontSize: 12.5 }}>The formula service is not available on this server yet. You can still write a formula and set it; the backend will use it once signals are enabled.</div></div>
        ) : null}

        <div className="sig-grid">
          <section className="card" style={{ height: "auto" }}>
            <header className="card-h"><div><h3>Formula</h3><span className="sub">Operators and fields autocomplete as you type. Ranks and z-scores are cross-sectional, per month.</span></div></header>
            <div className="card-b">
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Signal name" style={{ marginBottom: 8, fontWeight: 500 }} />
              <FormulaEditor value={expr} onChange={setExpr} error={check && !check.ok ? check.error : null} words={[...(ops.data ?? []).map((o) => ({ w: o.name, hint: `${o.name}(${o.args.join(", ")})`, doc: o.doc })), ...(fields.data ?? []).map((f) => ({ w: f.name, hint: `${f.source} · ${Math.round(f.coverage * 100)}% coverage`, doc: f.doc }))]} />
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, color: check?.ok ? "var(--up)" : check ? "var(--down)" : "var(--text-3)" }}>
                  {checking ? "Checking…" : check?.ok ? <><Check size={12} /> Valid · {check.preview.n_names} names · {check.preview.months} months</> : check && !check.ok ? check.error.message : "Not checked yet"}
                </span>
                <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                  <button className="btn sm ghost" onClick={() => void saveSignal(name, expr, active.projectId ?? undefined)} disabled={!check?.ok}><Save size={12} />Save version</button>
                  {active.expr ? <button className="btn sm ghost" onClick={() => active.set({ expr: null, name: null })}><X size={12} />Clear</button> : null}
                  <button className="btn primary sm" onClick={use} disabled={!check?.ok && !offline}>{isActive ? <><Check size={12} />In use</> : "Use this signal"}</button>
                  <Link className="btn sm" href="/research/report" onClick={use}><ClipboardCheck size={12} />Run report card</Link>
                </span>
              </div>
            </div>
          </section>

          <section className="card" style={{ height: "auto" }}>
            <header className="card-h"><div><h3>Preview</h3><span className="sub">What the signal looks like before any test</span></div></header>
            <div className="card-b"><PreviewPanel check={check} expr={check?.ok ? expr : null} /></div>
          </section>
        </div>

        <section className="card" style={{ height: "auto", marginTop: 12 }}>
          <header className="card-h">
            <Segmented label="Signal sources" value={tab} onChange={setTab} options={[{ value: "library", label: "Published anomalies" }, { value: "saved", label: "Saved" }, { value: "combine", label: "Combine" }, { value: "reference", label: "Reference" }]} />
          </header>
          <div className="card-b">
            {tab === "library" ? <LibraryList onPick={(s) => { setExpr(s.formula); setName(s.name); }} /> : null}
            {tab === "saved" ? <SavedList onPick={(e, n) => { setExpr(e); setName(n); }} /> : null}
            {tab === "combine" ? <Combine current={expr} onResult={(e) => { setExpr(e); setName("Combined signal"); }} /> : null}
            {tab === "reference" ? <Reference /> : null}
          </div>
        </section>
      </div>
    </div>
  );
}

type Word = { w: string; hint: string; doc: string };

/** Textarea with token autocomplete (Tab or Enter accepts) and the error span underlined. */
function FormulaEditor({ value, onChange, error, words }: { value: string; onChange: (v: string) => void; error: { message: string; start?: number; end?: number } | null; words: Word[] }) {
  const ta = useRef<HTMLTextAreaElement>(null);
  const [caret, setCaret] = useState(0);
  const [pick, setPick] = useState(0);
  const token = value.slice(0, caret).match(/[A-Za-z_][A-Za-z0-9_]*$/)?.[0] ?? "";
  const hits = token.length >= 1 ? words.filter((w) => w.w.startsWith(token) && w.w !== token).slice(0, 8) : [];
  const accept = (w: string) => {
    const before = value.slice(0, caret - token.length), after = value.slice(caret);
    const next = before + w + after;
    onChange(next);
    const pos = before.length + w.length;
    requestAnimationFrame(() => { ta.current?.setSelectionRange(pos, pos); setCaret(pos); });
  };
  return (
    <div style={{ position: "relative" }}>
      <textarea ref={ta} className="input formula" spellCheck={false} rows={4} value={value} aria-label="Signal formula"
        onChange={(e) => { onChange(e.target.value); setCaret(e.target.selectionStart); setPick(0); }}
        onKeyUp={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
        onClick={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
        onKeyDown={(e) => {
          if (!hits.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setPick((p) => (p + 1) % hits.length); }
          if (e.key === "ArrowUp") { e.preventDefault(); setPick((p) => (p - 1 + hits.length) % hits.length); }
          if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); accept(hits[pick]?.w ?? hits[0].w); }
        }} />
      {error && error.start !== undefined ? (
        <div className="formula-err" aria-hidden>{value.slice(0, error.start)}<u>{value.slice(error.start, error.end ?? error.start + 1) || " "}</u></div>
      ) : null}
      {hits.length ? (
        <div className="menu" role="listbox" style={{ position: "absolute", left: 8, top: "100%", zIndex: 5, width: 360, marginTop: 4 }}>
          {hits.map((h, i) => (
            <button key={h.w} type="button" role="option" aria-selected={i === pick} className="item" onMouseDown={(e) => { e.preventDefault(); accept(h.w); }} style={{ display: "grid", gap: 2, height: "auto", padding: "6px 10px", textAlign: "left", background: i === pick ? "var(--panel-2)" : undefined }}>
              <span className="num" style={{ color: "var(--text)" }}>{h.hint}</span>
              {h.doc ? <span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{h.doc}</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PreviewPanel({ check, expr }: { check: Validation | null; expr: string | null }) {
  const lit = useLiterature(expr);
  if (!check || !check.ok) return <div style={{ color: "var(--text-3)", fontSize: 12.5 }}>A valid formula shows its distribution, monthly coverage and its correlation with known factors here.</div>;
  const p = check.preview;
  const low = p.coverage.filter((c) => c.share < 0.5).length;
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div>
        <div className="insp-h">Distribution (pooled)</div>
        <Bars bars={p.histogram.map((b) => ({ label: Number(((b.x0 + b.x1) / 2).toPrecision(2)).toString(), value: b.count }))} height={130} signed={false} hideLabels={p.histogram.length > 20} valueLabels={false} />
      </div>
      <div>
        <div className="insp-h">Coverage by month {low ? <span style={{ color: "var(--warn)" }}>· {low} months below 50%</span> : null}</div>
        <div className="cov-strip">{p.coverage.map((c) => <span key={c.month} title={`${c.month}: ${Math.round(c.share * 100)}%`} style={{ opacity: 0.25 + 0.75 * c.share, background: c.share < 0.5 ? "var(--warn)" : "var(--accent)" }} />)}</div>
      </div>
      <div>
        <div className="insp-h">Closest known signals</div>
        {[...new Map([...p.corr_known, ...(lit.data ?? []).map((l) => ({ name: l.name, corr: l.corr }))].map((c) => [c.name.toLowerCase(), { ...c, name: label(c.name) }])).values()].sort((a, b) => Math.abs(b.corr) - Math.abs(a.corr)).slice(0, 6).map((c) => (
          <div key={c.name} className="kv-row"><span>{c.name}</span><b className="num" style={{ color: Math.abs(c.corr) > 0.7 ? "var(--warn)" : "var(--text)" }}>{c.corr.toFixed(2)}</b></div>
        ))}
        {p.corr_known.some((c) => Math.abs(c.corr) > 0.7) ? <p style={{ fontSize: 12, color: "var(--warn)", marginTop: 6 }}>Correlation above 0.7 with a known signal: test the residual with “orthogonalize against” in the study settings.</p> : null}
      </div>
    </div>
  );
}

function LibraryList({ onPick }: { onPick: (s: LibrarySignal) => void }) {
  const lib = useLibrary();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");
  const cats = useMemo(() => ["All", ...new Set((lib.data ?? []).map((s) => s.category))], [lib.data]);
  if (lib.isError) return <div style={{ color: "var(--text-3)", fontSize: 12.5 }}>The anomaly library is not available on this server yet.</div>;
  const rows = (lib.data ?? []).filter((s) => (cat === "All" || s.category === cat) && (!q || `${s.name} ${s.citation} ${s.formula}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <label className="search-in"><Search size={13} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search anomalies, authors, formulas" aria-label="Search anomalies" /></label>
        <div className="xpills">{cats.map((c) => <button key={c} className="pill" aria-pressed={cat === c} onClick={() => setCat(c)}>{c}</button>)}</div>
      </div>
      <table className="tbl">
        <thead><tr><th>Anomaly</th><th>Category</th><th>Formula</th><th>Source</th><th style={{ width: 70 }}>Sign</th><th style={{ width: 70 }} /></tr></thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td className="strong">{s.name}</td><td>{s.category}</td>
              <td className="num" style={{ maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text-2)" }} title={s.formula}>{s.formula}</td>
              <td style={{ color: "var(--text-3)" }}>{s.citation}</td>
              <td>{s.expected_sign > 0 ? "+" : "−"}</td>
              <td><button className="btn sm ghost" onClick={() => onPick(s)}>Load</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SavedList({ onPick }: { onPick: (expr: string, name: string) => void }) {
  const saved = useSavedSignals();
  const [open, setOpen] = useState<string | null>(null);
  const detail = useSavedSignal(open);
  if (saved.isError) return <div style={{ color: "var(--text-3)", fontSize: 12.5 }}>Saved signals are not available on this server yet.</div>;
  if (!saved.data?.length) return <div style={{ color: "var(--text-3)", fontSize: 12.5 }}>Save a formula to keep every version of it here.</div>;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 300px) 1fr", gap: 14 }}>
      <div>{saved.data.map((s) => <button key={s.id} className="nav-item" aria-current={open === s.id ? "page" : undefined} onClick={() => setOpen(s.id)} style={{ width: "100%" }}><span className="label">{s.name}</span><span className="num" style={{ marginLeft: "auto", color: "var(--text-4)" }}>v{s.latest_version}</span></button>)}</div>
      <div>
        {detail.data ? detail.data.versions.slice().reverse().map((v, i, all) => (
          <div key={v.version} className="kv-row" style={{ alignItems: "flex-start", gap: 12 }}>
            <span className="num" style={{ width: 40 }}>v{v.version}</span>
            <code style={{ flex: 1, fontSize: 12, whiteSpace: "pre-wrap" }}>{v.expr}{i < all.length - 1 && all[i + 1].expr !== v.expr ? <span style={{ color: "var(--text-4)" }}>{"  ← changed"}</span> : null}</code>
            <button className="btn sm ghost" onClick={() => onPick(v.expr, detail.data!.name)}>Load</button>
          </div>
        )) : <span style={{ color: "var(--text-3)", fontSize: 12.5 }}>Pick a saved signal to see its versions.</span>}
      </div>
    </div>
  );
}

function Combine({ current, onResult }: { current: string; onResult: (e: string) => void }) {
  const lib = useLibrary();
  const [parts, setParts] = useState<string[]>([current]);
  const [method, setMethod] = useState("equal");
  const [err, setErr] = useState<string | null>(null);
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <p style={{ fontSize: 12.5, color: "var(--text-3)" }}>Blend signals into one. Equal weight, by information coefficient, by inverse variance, or by averaging ranks.</p>
      {parts.map((p, i) => (
        <div key={i} style={{ display: "flex", gap: 6 }}>
          <input className="input num" value={p} onChange={(e) => setParts((ps) => ps.map((x, j) => (j === i ? e.target.value : x)))} aria-label={`Signal ${i + 1}`} style={{ flex: 1 }} />
          <button className="btn sm icon ghost" aria-label="Remove" onClick={() => setParts((ps) => ps.filter((_, j) => j !== i))}><X size={12} /></button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select className="input" style={{ width: 260, height: 30 }} aria-label="Add a published anomaly" value="" onChange={(e) => e.target.value && setParts((ps) => [...ps, e.target.value])}>
          <option value="">Add a published anomaly…</option>
          {(lib.data ?? []).map((s) => <option key={s.id} value={s.formula}>{s.name}</option>)}
        </select>
        <button className="btn sm ghost" onClick={() => setParts((ps) => [...ps, ""])}><Layers size={12} />Add formula</button>
        <Segmented label="Weighting" value={method} onChange={setMethod} options={[{ value: "equal", label: "Equal" }, { value: "ic", label: "IC" }, { value: "inverse_variance", label: "Inv. var" }, { value: "rank_average", label: "Rank avg" }]} />
        <button className="btn primary sm" style={{ marginLeft: "auto" }} disabled={parts.filter(Boolean).length < 2}
          onClick={() => combineExprs(parts.filter(Boolean), method).then((r) => { setErr(null); onResult(r.expr); }).catch((e: Error) => setErr(e.message))}>
          <Sparkles size={12} />Combine
        </button>
      </div>
      {err ? <span style={{ color: "var(--down)", fontSize: 12 }}>{err}</span> : null}
    </div>
  );
}

function Reference() {
  const ops = useOperators();
  const fields = useFields();
  const groups = useMemo(() => Object.entries((ops.data ?? []).reduce<Record<string, typeof ops.data>>((a, o) => ({ ...a, [o.category]: [...(a[o.category] ?? []), o] }), {})), [ops.data]);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
      {groups.map(([cat, list]) => (
        <div key={cat}>
          <div className="insp-h"><BookOpen size={12} /> {label(cat)}</div>
          {(list ?? []).map((o) => <div key={o.name} className="kv-row" style={{ display: "grid", gap: 2 }}><code className="num">{o.name}({o.args.join(", ")})</code><span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{o.doc} {o.example ? <code>e.g. {o.example}</code> : null}</span></div>)}
        </div>
      ))}
      {fields.data?.length ? (
        <div>
          <div className="insp-h">Fields</div>
          {fields.data.map((f) => <div key={f.name} className="kv-row"><code className="num">{f.name}</code><span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{f.source} · {Math.round(f.coverage * 100)}%</span></div>)}
        </div>
      ) : null}
    </div>
  );
}
