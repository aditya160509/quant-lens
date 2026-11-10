"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Globe2, Plus, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { get } from "@/modules/research/api";
import { FilterChips, isRangeField } from "@/modules/research/FilterChips";
import type { FeatureRun } from "@/modules/research/ResearchApp";
import { lab } from "@/modules/research/lab";
import { label as fmtLabel } from "@/modules/research/format";
import type { FeatureSpec } from "@/modules/research/types";
import { searchSymbols, usePopular, type SymbolHit } from "@/kit/QuickLookData";
import { PopMenu, type MenuAt } from "@/workspace/ui";
import { send } from "../api";
import { useWatchlists } from "../watchlists";
import { toPayload } from "@/modules/research/StudyForm";
import { AddFilter } from "./AddFilter";
import { InFilter, picked } from "./InFilter";
import { HistogramRange, stageFor, useFilterColumns, useFilterPreview } from "./Preview";
import "./universe.css";

const CAP = 1000;
const CATS = ["sector", "industry", "country", "exchange", "currency"];
const SIZES = [25, 50, 100, 250, 500, 1000];
const PERIODS: [string, number][] = [["6M", 182], ["1Y", 365], ["2Y", 756], ["3Y", 1095], ["5Y", 1825], ["10Y", 3650]];
const QUICK = ["market_cap", "pe", "roe", "revenue_growth_yoy", "dividend_yield", "return_12m", "rsi", "beta"];
const ALL = new Set(["", "master", "all", "default"]);
type Saved = { universe_id: string; name: string; symbols: string[]; count: number };

const parse = (v: unknown) => { const s = Array.isArray(v) ? v.join(",") : String(v ?? ""); return ALL.has(s.trim().toLowerCase()) ? [] : s.split(/[,;\s]+/).filter(Boolean); };

export function UniverseBar({ feature, run }: { feature: FeatureSpec; run: FeatureRun }) {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState<{ key: string; at: MenuAt } | null>(null);
  const keys = new Set(feature.inputs.map((f) => f.key));
  const tickers = parse(run.form.universe);
  const size = Math.min(Number(run.form.max_symbols ?? 500) || 500, CAP);
  const set = (k: string, v: unknown) => run.setForm((c) => ({ ...c, [k]: v }));
  // Forms saved before the cap still hold 5000.
  const over = Number(run.form.max_symbols ?? 0) > CAP;
  useEffect(() => { if (over) run.setForm((c) => ({ ...c, max_symbols: 500 })); }, [over, run.setForm]); // eslint-disable-line react-hooks/exhaustive-deps
  const days = Number(run.form.lookback_days ?? 756);
  const range = useMemo(() => feature.inputs.filter(isRangeField), [feature]);
  const metrics = QUICK.filter((m) => keys.has(`${m}_min`));
  const added = [...new Set(range.map((f) => f.key.replace(/_(min|max|top)$/, "")))].filter((m) => !QUICK.includes(m) && (run.form[`${m}_min`] || run.form[`${m}_max`]));
  const name = (m: string) => range.find((f) => f.key === `${m}_min`)?.label.replace(/ (Min|Max)$/, "") ?? fmtLabel(m);
  const at = (e: React.MouseEvent, key: string) => { const r = e.currentTarget.getBoundingClientRect(); setMenu({ key, at: { x: r.left, y: r.bottom + 6 } }); };
  const columnOf = useFilterColumns();
  const shownMetrics = [...metrics, ...added];
  const preview = useFilterPreview(toPayload(feature, run.form), [...shownMetrics, ...(menu && menu.key !== "+" && !menu.key.startsWith("cat:") ? [menu.key] : [])].map((m) => columnOf[m]).filter(Boolean)).data;
  const cats = feature.inputs.filter((f) => CATS.includes(f.key));
  const catPill = (f: (typeof cats)[number]) => {
    const n = picked(run.form[f.key]).length;
    return <button key={f.key} type="button" className={`ub-pill${n ? " on" : ""}`} onClick={(e) => at(e, `cat:${f.key}`)}>{f.label}{n ? <b>{n === 1 ? picked(run.form[f.key])[0] : `${n} chosen`}</b> : null}<ChevronDown size={12} /></button>;
  };
  const catMenu = menu?.key.startsWith("cat:") ? cats.find((f) => f.key === menu.key.slice(4)) : undefined;
  const pill = (m: string) => {
    const lo = run.form[`${m}_min`], hi = run.form[`${m}_max`];
    const on = Boolean(lo || hi);
    const st = on ? stageFor(preview, m) : undefined;
    return <button key={m} type="button" className={`ub-pill${on ? " on" : ""}`} onClick={(e) => at(e, m)}>{name(m)}{on ? <b>{String(lo || "…")}–{String(hi || "…")}</b> : null}{st ? <em className="ub-cut num" title={`${st.removed} removed, ${st.remaining} left`}>−{st.removed}</em> : null}<ChevronDown size={12} /></button>;
  };

  return (
    <div className="ub">
      <div className="ub-row">
        {keys.has("universe") ? (
          <button type="button" className="ub-title" onClick={() => setOpen(true)}>
            <Globe2 size={17} /><span>{tickers.length ? `${tickers.length} stocks` : `Top ${size.toLocaleString()} by liquidity`}</span><ChevronDown size={15} />
          </button>
        ) : null}
        {keys.has("lookback_days") ? (
          <div className="ub-seg" role="radiogroup" aria-label="Period">
            {PERIODS.map(([l, d]) => <button key={l} type="button" role="radio" aria-checked={days === d} onClick={() => set("lookback_days", d)}>{l}</button>)}
          </div>
        ) : null}
        {keys.has("as_of_date") ? <input className="ub-date" type="date" aria-label="As of date" value={String(run.form.as_of_date ?? "")} onChange={(e) => set("as_of_date", e.target.value)} /> : null}
        {run.stale ? <span className="sh-pill amber">Changed</span> : null}
      </div>
      {range.length ? (
        <div className="ub-row">
          {cats.map(catPill)}{metrics.map(pill)}{added.map(pill)}
          <button type="button" className="ub-pill add" aria-label="All filters" onClick={(e) => at(e, "+")}><Plus size={13} />Filter</button>
          {preview ? <span className="ub-pass num" role="status"><b>{preview.passed.toLocaleString()}</b> of {preview.universe.toLocaleString()} pass</span> : null}
        </div>
      ) : null}
      <PopMenu at={menu?.at ?? null} onClose={() => setMenu(null)} width={menu?.key === "+" ? 440 : 300} sticky>
        {catMenu ? (
          <div style={{ padding: 10 }}><InFilter field={catMenu} value={run.form[catMenu.key]} onChange={(v) => set(catMenu.key, v)} /></div>
        ) : menu?.key === "+" ? (
          <><AddFilter fields={range} active={new Set(shownMetrics.filter((m) => run.form[`${m}_min`] || run.form[`${m}_max`]))} name={name} onPick={(m) => setMenu((cur) => (cur ? { key: m, at: cur.at } : cur))} />
          <details className="af-exact"><summary>Exact values and top N</summary><div style={{ padding: 8, maxHeight: 360, overflowY: "auto" }}><FilterChips scope={feature.id} fields={range} form={run.form} setForm={run.setForm} /></div></details></>
        ) : menu ? (
          <div className="ub-range">
            <b>{name(menu.key)}</b>
            {columnOf[menu.key] ? <HistogramRange column={columnOf[menu.key]} dist={preview?.dist[columnOf[menu.key]]} min={run.form[`${menu.key}_min`]} max={run.form[`${menu.key}_max`]} onChange={(lo, hi) => run.setForm((c) => ({ ...c, [`${menu.key}_min`]: lo, [`${menu.key}_max`]: hi }))} /> : null}
            <div>
              <input className="input num" inputMode="decimal" placeholder="Min" aria-label="Minimum" value={String(run.form[`${menu.key}_min`] ?? "")} onChange={(e) => set(`${menu.key}_min`, e.target.value)} />
              <input className="input num" inputMode="decimal" placeholder="Max" aria-label="Maximum" value={String(run.form[`${menu.key}_max`] ?? "")} onChange={(e) => set(`${menu.key}_max`, e.target.value)} />
            </div>
          </div>
        ) : null}
      </PopMenu>
      {open ? <Picker tickers={tickers} size={size} onClose={() => setOpen(false)} onApply={(list, n) => { run.setForm((c) => ({ ...c, universe: list.length ? list.join(",") : "master", max_symbols: list.length ? Math.max(list.length, n) : n })); setOpen(false); }} /> : null}
    </div>
  );
}

function Picker({ tickers, size, onApply, onClose }: { tickers: string[]; size: number; onApply: (list: string[], n: number) => void; onClose: () => void }) {
  const qc = useQueryClient();
  const [list, setList] = useState(tickers);
  const [n, setN] = useState(size);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SymbolHit[]>([]);
  const [saving, setSaving] = useState("");
  const [err, setErr] = useState("");
  const popular = usePopular();
  const saved = useQuery({ queryKey: ["screener", "universes"], queryFn: () => get<{ universes: Saved[] }>("/universes"), retry: false });
  const lists = useWatchlists((s) => s.lists);
  useEffect(() => {
    if (!q.trim()) { setHits([]); return; }
    const c = new AbortController();
    const t = setTimeout(() => { searchSymbols(q, null, c.signal).then((r: { results?: SymbolHit[] }) => setHits(r.results ?? [])).catch(() => undefined); }, 90);
    return () => { clearTimeout(t); c.abort(); };
  }, [q]);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  const shown = q.trim() ? hits : (popular.data?.results ?? []);
  const full = list.length >= CAP;
  const toggle = (t: string) => setList((c) => (c.includes(t) ? c.filter((x) => x !== t) : c.length >= CAP ? c : [...c, t]));
  const merge = (more: string[]) => setList((c) => [...new Set([...c, ...more])].slice(0, CAP));
  const save = () => { const name = saving.trim(); if (name && list.length) void send("PUT", `/universes/u${Date.now().toString(36)}`, { name, symbols: list }).then(() => { setSaving(""); return qc.invalidateQueries({ queryKey: ["screener", "universes"] }); }); };

  return (
    <div className="ub-over" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="ub-dlg" role="dialog" aria-modal="true" aria-label="Universe">
        <label className="ub-search"><Search size={17} /><input autoFocus placeholder="Add any stock" value={q} onChange={(e) => setQ(e.target.value)} /><button type="button" aria-label="Close" onClick={onClose}><X size={15} /></button></label>
        <div className="ub-body">
          <div className="ub-results">
            {shown.map((h) => {
              const on = list.includes(h.ticker);
              return (
                <button key={h.ticker} type="button" className="ub-hit" disabled={full && !on} aria-pressed={on} onClick={() => toggle(h.ticker)}>
                  <span className="ub-mono">{h.ticker.slice(0, 2)}</span>
                  <span className="ub-co"><b>{h.ticker}</b><small>{h.company_name ?? ""}</small></span>
                  <em>{h.sector ?? h.exchange}</em>
                  {on ? <Check size={15} /> : <Plus size={15} />}
                </button>
              );
            })}
          </div>
          <aside className="ub-side">
            <h4>Size</h4>
            <div className="ub-sizes">{SIZES.map((s) => <button key={s} type="button" aria-pressed={!list.length && n === s} onClick={() => { setList([]); setN(s); }}>{s.toLocaleString()}</button>)}</div>
            <h4>Saved</h4>
            <div className="ub-saved">
              {(saved.data?.universes ?? []).map((u) => <button key={u.universe_id} type="button" onClick={() => merge(u.symbols)}>{u.name}<em>{u.count}</em></button>)}
              {Object.entries(lists).filter(([, l]) => l.length).map(([id, l]) => <button key={id} type="button" onClick={() => merge(l)}>{id}<em>{l.length}</em></button>)}
            </div>
            <h4>Paste</h4>
            <input type="file" accept=".csv,text/csv" aria-label="Upload CSV" onChange={(e) => { const f = e.target.files?.[0]; if (!f) return; const body = new FormData(); body.append("file", f); void fetch(`${lab().base}/uploads`, { method: "POST", body }).then((r) => r.json()).then((j: { symbols?: string[]; detail?: string }) => { if (j.symbols) merge(j.symbols); else setErr(typeof j.detail === "string" ? j.detail : "Upload failed"); }).catch(() => setErr("Upload failed")); e.target.value = ""; }} />
            {err ? <small role="alert">{err}</small> : null}
            <textarea className="input" rows={2} placeholder="AAPL, MSFT" onBlur={(e) => { const v = e.target.value.toUpperCase().split(/[,;\s]+/).filter(Boolean); if (v.length) { merge(v); e.target.value = ""; } }} />
            {list.length ? (
              <>
                <h4>Chosen <em>{list.length}/{CAP}</em></h4>
                <div className="ub-chips">{list.slice(0, 80).map((t) => <button key={t} type="button" onClick={() => toggle(t)}>{t}<X size={11} /></button>)}</div>
                <div className="ub-save"><input className="input" placeholder="Name" value={saving} onChange={(e) => setSaving(e.target.value)} /><button type="button" className="btn sm" disabled={!saving.trim()} onClick={save}>Save</button></div>
              </>
            ) : null}
          </aside>
        </div>
        <footer className="ub-foot">
          <span>{list.length ? `${list.length} stocks` : `Top ${n.toLocaleString()} by liquidity`}</span>
          {list.length ? <button type="button" className="btn ghost" onClick={() => setList([])}>Clear</button> : null}
          <button type="button" className="btn primary" onClick={() => onApply(list, n)}>Use universe</button>
        </footer>
      </div>
    </div>
  );
}
