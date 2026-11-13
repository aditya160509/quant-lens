"use client";

import { useScreenerPalette } from "../palette";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Check, ChevronDown, Eye, EyeOff, Globe2, Link2, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import toast from "react-hot-toast";
import { featureHref } from "@/modules/research/catalog";
import { encodeSettings } from "@/modules/research/StudyForm";
import { useEffect, useMemo, useRef, useState } from "react";
import { get } from "@/modules/research/api";
import { FilterChips, isRangeField } from "@/modules/research/FilterChips";
import type { FeatureRun } from "@/modules/research/ResearchApp";
import { lab } from "@/modules/research/lab";
import { label as fmtLabel } from "@/modules/research/format";
import type { FeatureSpec, RunRecord } from "@/modules/research/types";
import { useRuns } from "@/modules/research/api";
import { searchSymbols, usePopular, type SymbolHit } from "@/kit/QuickLookData";
import { PopMenu, type MenuAt } from "@/workspace/ui";
import { send } from "../api";
import { useWatchlists } from "../watchlists";
import { toPayload } from "@/modules/research/StudyForm";
import { DatePick } from "@/kit/DatePick";
import { AddFilter } from "./AddFilter";
import { InFilter, picked } from "./InFilter";
import { HistogramRange, MixBar, stageFor, useFilterColumns, useFilterPreview } from "./Preview";
import "./universe.css";

const CAP = 1000;
const REBAL: [string, string, number][] = [["Weekly", "weekly", 5], ["Monthly", "monthly", 21], ["Quarterly", "quarterly", 63]];
const TOPN = [10, 20, 50, 100];
const CATS = ["sector", "industry", "country", "exchange", "currency"];
const SIZES = [25, 50, 100, 250, 500, 1000];
const BASIS: [string, string][] = [["liquidity", "Liquidity"], ["market_cap", "Market cap"], ["coverage", "Data coverage"]];
const EUROPE = ["United Kingdom", "Germany", "France", "Italy", "Switzerland", "Sweden", "Finland"];
const PRESETS: [string, Record<string, unknown>][] = [
  ["United States", { country: ["United States"] }], ["India", { country: ["India"] }], ["Europe", { country: EUROPE }], ["Asia Pacific", { country: ["Japan", "South Korea", "Taiwan", "Hong Kong", "Australia", "Singapore", "China"] }],
  ["Mega cap", { market_cap_min: "200000000000", market_cap_max: "" }], ["Large cap", { market_cap_min: "10000000000", market_cap_max: "200000000000" }],
  ["Mid cap", { market_cap_min: "2000000000", market_cap_max: "10000000000" }], ["Small cap", { market_cap_min: "300000000", market_cap_max: "2000000000" }],
];
const PRESET_KEYS = ["country", "market_cap_min", "market_cap_max"];
/** Seconds from the dock log line "Completed in 2.3s". */
const secsOf = (r: RunRecord) => Number(r.log?.find((l) => l.text.startsWith("Completed in"))?.text.match(/([\d.]+)s/)?.[1]);
const PERIODS: [string, number][] = [["6M", 182], ["1Y", 365], ["2Y", 756], ["3Y", 1095], ["5Y", 1825], ["10Y", 3650]];
const QUICK = ["market_cap", "pe", "roe", "revenue_growth_yoy", "dividend_yield", "return_12m", "rsi", "beta"];
const ALL = new Set(["", "master", "all", "default"]);
type Saved = { universe_id: string; name: string; symbols: string[]; count: number };
type DataRange = { first: string; last: string; names: number; years: { year: number; names: number }[] };
const DAY = 86_400_000;
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);

const parse = (v: unknown) => { const s = Array.isArray(v) ? v.join(",") : String(v ?? ""); return ALL.has(s.trim().toLowerCase()) ? [] : s.split(/[,;\s]+/).filter(Boolean); };

export function UniverseBar({ feature, run }: { feature: FeatureSpec; run: FeatureRun }) {
  const [open, setOpen] = useState(false);
  useScreenerPalette();
  const [menu, setMenu] = useState<{ key: string; at: MenuAt } | null>(null);
  const keys = new Set(feature.inputs.map((f) => f.key));
  const tickers = parse(run.form.universe);
  const size = Math.min(Number(run.form.max_symbols ?? 500) || 500, CAP);
  const set = (k: string, v: unknown) => run.setForm((c) => ({ ...c, [k]: v }));
  // Forms saved before the cap still hold 5000.
  const over = Number(run.form.max_symbols ?? 0) > CAP;
  useEffect(() => { if (over) run.setForm((c) => ({ ...c, max_symbols: 500 })); }, [over, run.setForm]); // eslint-disable-line react-hooks/exhaustive-deps
  const days = Number(run.form.lookback_days ?? 756);
  const span = useQuery({ queryKey: ["screener", "data-range"], queryFn: () => get<DataRange>("/data-range"), staleTime: Infinity, retry: false }).data;
  const end = String(run.form.as_of_date || span?.last || "");
  const start = end ? iso(Date.parse(end) - days * DAY) : "";
  const maxDays = span && end ? Math.round((Date.parse(end) - Date.parse(span.first)) / DAY) : null;
  const custom = !PERIODS.some(([, d]) => d === days) && days !== maxDays;
  const range = useMemo(() => feature.inputs.filter(isRangeField), [feature]);
  const metrics = QUICK.filter((m) => keys.has(`${m}_min`));
  // A filter switched off keeps its bounds under "off:" so switching it on restores them; toPayload ignores the key.
  const offOf = (m: string) => run.form[`off:${m}`] as [unknown, unknown] | undefined;
  const toggle = (m: string) => run.setForm((c) => {
    const off = c[`off:${m}`] as [unknown, unknown] | undefined;
    const next = { ...c };
    if (off) { next[`${m}_min`] = off[0]; next[`${m}_max`] = off[1]; delete next[`off:${m}`]; }
    else { next[`off:${m}`] = [c[`${m}_min`] ?? "", c[`${m}_max`] ?? ""]; next[`${m}_min`] = ""; next[`${m}_max`] = ""; }
    return next;
  });
  const added = [...new Set(range.map((f) => f.key.replace(/_(min|max|top)$/, "")))].filter((m) => !QUICK.includes(m) && (run.form[`${m}_min`] || run.form[`${m}_max`] || offOf(m)));
  const name = (m: string) => range.find((f) => f.key === `${m}_min`)?.label.replace(/ (Min|Max)$/, "") ?? fmtLabel(m);
  // A second click on the open chip closes it: the outside press already closed it, so skip the reopen.
  const shut = useRef({ key: "", t: 0 });
  const at = (e: React.MouseEvent, key: string) => {
    if (menu?.key === key || (shut.current.key === key && Date.now() - shut.current.t < 400)) { setMenu(null); return; }
    const r = e.currentTarget.getBoundingClientRect(); setMenu({ key, at: { x: r.left, y: r.bottom + 6 } });
  };
  // Shift+F opens the filter picker, F the first table's columns; never while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const hot = e.key === "F" ? "f" : e.key === "f" ? "col" : null;
      if (hot) { e.preventDefault(); document.querySelector<HTMLButtonElement>(`[data-hotkey='${hot}']`)?.click(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  // Auto re-runs after a pause in editing, only on small universes so a run stays a few seconds.
  const small = (tickers.length || size) <= 250;
  const [auto, setAuto] = useState(() => { try { return localStorage.getItem("screener-auto-run") === "1"; } catch { return false; } });
  const formKey = JSON.stringify(run.form);
  const [seenKey, setSeenKey] = useState(formKey);
  useEffect(() => {
    if (!auto || !small || formKey === seenKey || run.status === "running" || run.status === "queued") return;
    const id = setTimeout(() => { setSeenKey(formKey); run.run(); }, 900);
    return () => clearTimeout(id);
  }, [auto, small, formKey, seenKey, run]);
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem("screener-filters-hidden") === "1"; } catch { return false; } });
  const toggleHidden = () => { const next = !hidden; setHidden(next); try { localStorage.setItem("screener-filters-hidden", next ? "1" : "0"); } catch { /* storage blocked */ } };
  const qc = useQueryClient();
  const fid = feature.id.replace(/^sc/, "");
  const presets = (useQuery({ queryKey: ["screener", "screens"], queryFn: () => get<{ screens: { screen_id: string; name: string; feature_id: string; payload: Record<string, unknown> }[] }>("/screens"), retry: false }).data?.screens ?? []).filter((x) => x.feature_id === fid);
  const saveScreen = () => {
    const name = window.prompt("Save screen as")?.trim();
    if (name) void send("PUT", `/screens/s${Date.now().toString(36)}`, { name, feature_id: fid, payload: toPayload(feature, run.form) }).then(() => { toast.success(`Saved ${name}`); return qc.invalidateQueries({ queryKey: ["screener", "screens"] }); }).catch((e: Error) => toast.error(e.message));
  };
  const basis = String(run.form.rank_by ?? "liquidity");
  // Estimated run time: the last finished run of this study, scaled by universe size.
  const last = useRuns((st) => st.runs.find((r) => r.featureId === feature.id && r.status === "completed" && Number.isFinite(secsOf(r))));
  const names = tickers.length || size;
  const lastNames = last ? parse(last.payload?.universe).length || Number(last.payload?.max_symbols ?? 500) : 0;
  const eta = last && lastNames ? Math.max(1, Math.round((secsOf(last) * names) / lastNames)) : null;
  const columnOf = useFilterColumns();
  const shownMetrics = [...metrics, ...added];
  const preview = useFilterPreview(toPayload(feature, run.form), [...shownMetrics, ...(menu?.key === "+" ? Object.keys(columnOf) : menu && !menu.key.startsWith("cat:") ? [menu.key] : [])].map((m) => columnOf[m]).filter(Boolean)).data;
  const cats = feature.inputs.filter((f) => CATS.includes(f.key));
  const catPill = (f: (typeof cats)[number]) => {
    const n = picked(run.form[f.key]).length;
    return <button key={f.key} type="button" className={`ub-pill${n ? " on" : ""}`} onClick={(e) => at(e, `cat:${f.key}`)}>{f.label}{n ? <b>{n === 1 ? picked(run.form[f.key])[0] : `${n} chosen`}</b> : null}<ChevronDown size={12} /></button>;
  };
  const catMenu = menu?.key.startsWith("cat:") ? cats.find((f) => f.key === menu.key.slice(4)) : undefined;
  const pill = (m: string) => {
    const off = offOf(m);
    const lo = off ? off[0] : run.form[`${m}_min`], hi = off ? off[1] : run.form[`${m}_max`];
    const on = Boolean(lo || hi) && !off;
    const st = on ? stageFor(preview, m) : undefined;
    return <button key={m} type="button" className={`ub-pill${on ? " on" : ""}${off ? " off" : ""}`} onClick={(e) => at(e, m)}>{name(m)}{lo || hi ? <b>{String(lo || "…")}–{String(hi || "…")}</b> : null}{st ? <em className="ub-cut num" title={`${st.removed} removed, ${st.remaining} left`}>−{st.removed}</em> : null}<ChevronDown size={12} /></button>;
  };

  return (
    <div className="ub">
      <div className="ub-row">
        {keys.has("universe") ? (
          <button type="button" className="ub-title" onClick={() => setOpen(true)}>
            <Globe2 size={17} /><span>{tickers.length ? `${tickers.length} stocks` : `Top ${size.toLocaleString()} by ${BASIS.find(([k]) => k === basis)?.[1].toLowerCase() ?? "liquidity"}`}</span><ChevronDown size={15} />
          </button>
        ) : null}
        {keys.has("lookback_days") ? (
          <div className="ub-seg" role="radiogroup" aria-label="Period">
            {PERIODS.map(([l, d]) => <button key={l} type="button" role="radio" aria-checked={days === d} onClick={() => set("lookback_days", d)}>{l}</button>)}
            {maxDays ? <button type="button" role="radio" aria-checked={days === maxDays} onClick={() => set("lookback_days", maxDays)}>Max</button> : null}
            <button type="button" role="radio" aria-checked={custom} onClick={(e) => at(e, "period")}>{custom && start ? `${start} – ${end}` : "Custom"}</button>
          </div>
        ) : null}
        {keys.has("rebalance_frequency") ? (
          <div className="ub-seg" role="radiogroup" aria-label="Rebalance">
            {REBAL.map(([l, f, d]) => <button key={f} type="button" role="radio" aria-checked={(run.form.rebalance_frequency ?? "monthly") === f} onClick={() => run.setForm((c) => ({ ...c, rebalance_frequency: f, rebalance_days: d }))}>{l}</button>)}
          </div>
        ) : null}
        {keys.has("top_n") ? (
          <div className="ub-seg" role="radiogroup" aria-label="Names held">
            {TOPN.map((n) => <button key={n} type="button" role="radio" aria-checked={Number(run.form.top_n ?? 50) === n} onClick={() => set("top_n", n)}>Top {n}</button>)}
          </div>
        ) : null}
        {keys.has("as_of_date") ? <DatePick label="As of date" value={String(run.form.as_of_date ?? "")} min={span?.first} max={span?.last} onChange={(v) => set("as_of_date", v)} /> : null}
        {run.stale ? <span className="sh-pill amber">Changed</span> : null}
        {range.length ? <button type="button" className="btn sm icon ghost ub-hide" aria-pressed={hidden} aria-label={hidden ? "Show filters" : "Hide filters"} title={hidden ? "Show filters" : "Hide filters"} onClick={toggleHidden}>{hidden ? <Eye size={14} /> : <EyeOff size={14} />}</button> : null}
      </div>
      {presets.length ? (
        <div className="ub-row ub-presets">
          {presets.slice(-8).map((x) => <button key={x.screen_id} type="button" className="ub-chip" onClick={() => run.setForm((c) => ({ ...c, ...x.payload }))}>{x.name}</button>)}
        </div>
      ) : null}
      {range.length && !hidden ? (
        <div className="ub-row">
          {cats.map(catPill)}{metrics.map(pill)}{added.map(pill)}
          <button type="button" className="ub-pill add" data-hotkey="f" aria-keyshortcuts="Shift+F" aria-label="All filters" onClick={(e) => at(e, "+")}><Plus size={13} />Filter</button>
          <button type="button" className={`ub-pill${auto && small ? " on" : ""}`} aria-pressed={auto} disabled={!small} title={small ? "Re-run after each change" : "Auto run needs 250 names or fewer"} onClick={() => { const next = !auto; setAuto(next); try { localStorage.setItem("screener-auto-run", next ? "1" : "0"); } catch { /* storage blocked */ } }}>Auto</button>
          <button type="button" className="ub-pill" onClick={saveScreen}><Bookmark size={12} />Save</button>
          {preview ? <span className="ub-pass num" role="status"><MixBar mix={preview.mix?.sector} /><b>{preview.passed.toLocaleString()}</b> of {preview.universe.toLocaleString()} pass{eta ? <em title="From the last run of this study">≈{eta}s</em> : null}</span> : eta ? <span className="ub-pass num" role="status"><em title="From the last run of this study">≈{eta}s</em></span> : null}
        </div>
      ) : null}
      <PopMenu at={menu?.at ?? null} onClose={() => { shut.current = { key: menu?.key ?? "", t: Date.now() }; setMenu(null); }} width={menu?.key === "+" ? 440 : 300} sticky>
        {menu?.key === "period" ? (
          <div className="ub-range">
            <b>Period</b>
            <div>
              <DatePick label="Start" empty="Start" min={span?.first} max={end} value={start} onChange={(v) => { if (v && end) set("lookback_days", Math.max(1, Math.round((Date.parse(end) - Date.parse(v)) / DAY))); }} />
              <DatePick label="End" empty="End" min={span?.first} max={span?.last} value={end} onChange={(v) => { if (v && start) run.setForm((c) => ({ ...c, as_of_date: v, lookback_days: Math.max(1, Math.round((Date.parse(v) - Date.parse(start)) / DAY)) })); }} />
            </div>
            {span ? <YearStrip years={span.years} from={Number(start.slice(0, 4))} to={Number(end.slice(0, 4))} /> : null}
          </div>
        ) : catMenu ? (
          <div style={{ padding: 10 }}><InFilter field={catMenu} value={run.form[catMenu.key]} onChange={(v) => set(catMenu.key, v)} /></div>
        ) : menu?.key === "+" ? (
          <><AddFilter fields={range} empty={new Set(Object.keys(columnOf).filter((m) => preview?.dist[columnOf[m]]?.known === 0))} active={new Set(shownMetrics.filter((m) => run.form[`${m}_min`] || run.form[`${m}_max`]))} name={name} onPick={(m) => setMenu((cur) => (cur ? { key: m, at: cur.at } : cur))} />
          <details className="af-exact"><summary>Exact values and top N</summary><div style={{ padding: 8, maxHeight: 360, overflowY: "auto" }}><FilterChips scope={feature.id} fields={range} form={run.form} setForm={run.setForm} /></div></details></>
        ) : menu ? (
          <div className="ub-range">
            <b>{name(menu.key)}</b>
            {columnOf[menu.key] ? <HistogramRange column={columnOf[menu.key]} dist={preview?.dist[columnOf[menu.key]]} min={run.form[`${menu.key}_min`]} max={run.form[`${menu.key}_max`]} onChange={(lo, hi) => run.setForm((c) => ({ ...c, [`${menu.key}_min`]: lo, [`${menu.key}_max`]: hi }))} /> : null}
            <div>
              <input className="input num" inputMode="decimal" placeholder="Min" aria-label="Minimum" value={String(run.form[`${menu.key}_min`] ?? "")} onChange={(e) => set(`${menu.key}_min`, e.target.value)} />
              <input className="input num" inputMode="decimal" placeholder="Max" aria-label="Maximum" value={String(run.form[`${menu.key}_max`] ?? "")} onChange={(e) => set(`${menu.key}_max`, e.target.value)} />
            </div>
            <div className="ub-range-foot">
              {stageFor(preview, menu.key) ? <span className="num">−{stageFor(preview, menu.key)?.removed} · {stageFor(preview, menu.key)?.remaining} left</span> : <span />}
              <label className="ub-check" style={{ margin: 0 }}><input type="checkbox" checked={!offOf(menu.key)} disabled={!offOf(menu.key) && !run.form[`${menu.key}_min`] && !run.form[`${menu.key}_max`]} onChange={() => toggle(menu.key)} />On</label>
              <button type="button" className="btn sm ghost" disabled={!offOf(menu.key) && !run.form[`${menu.key}_min`] && !run.form[`${menu.key}_max`]} onClick={() => run.setForm((c) => { const n = { ...c, [`${menu.key}_min`]: "", [`${menu.key}_max`]: "" }; delete n[`off:${menu.key}`]; return n; })}>Remove</button>
            </div>
          </div>
        ) : null}
      </PopMenu>
      {open ? <Picker tickers={tickers} size={size} basis={basis} primary={Boolean(run.form.primary_only)} active={(f) => PRESET_KEYS.every((k) => k in f ? JSON.stringify(run.form[k] ?? "") === JSON.stringify(f[k]) : true)} onPatch={(patch) => run.setForm((c) => ({ ...c, ...patch }))} onClose={() => setOpen(false)} onApply={(list, n) => { run.setForm((c) => ({ ...c, universe: list.length ? list.join(",") : "master", max_symbols: list.length ? Math.max(list.length, n) : n })); setOpen(false); }} /> : null}
    </div>
  );
}

/** Names with prices in each year; the chosen range is lit. */
function YearStrip({ years, from, to }: { years: DataRange["years"]; from: number; to: number }) {
  const top = Math.max(1, ...years.map((y) => y.names));
  return (
    <div className="ub-years" role="img" aria-label={`Names with prices per year, ${years[0]?.year} to ${years.at(-1)?.year}`}>
      {years.map((y) => <i key={y.year} title={`${y.year}: ${y.names.toLocaleString()} names`} className={y.year >= from && y.year <= to ? "on" : undefined} style={{ height: `${Math.max(8, (y.names / top) * 100)}%` }} />)}
      <span className="num">{years[0]?.year}</span><span className="num">{years.at(-1)?.year}</span>
    </div>
  );
}

function Picker({ tickers, size, basis, primary, active, onPatch, onApply, onClose }: { tickers: string[]; size: number; basis: string; primary: boolean; active: (f: Record<string, unknown>) => boolean; onPatch: (patch: Record<string, unknown>) => void; onApply: (list: string[], n: number) => void; onClose: () => void }) {
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
  const refresh = () => qc.invalidateQueries({ queryKey: ["screener", "universes"] });
  const save = () => { const name = saving.trim(); if (name && list.length) void send("PUT", `/universes/u${Date.now().toString(36)}`, { name, symbols: list }).then(() => { setSaving(""); toast.success(`Saved ${name}`); return refresh(); }); };
  const rename = (u: Saved) => { const name = window.prompt("Rename universe", u.name)?.trim(); if (name && name !== u.name) void send("PUT", `/universes/${u.universe_id}`, { name, symbols: u.symbols }).then(refresh); };
  const remove = (u: Saved) => { if (window.confirm(`Delete ${u.name}?`)) void send("DELETE", `/universes/${u.universe_id}`).then(() => { toast.success(`Deleted ${u.name}`); return refresh(); }); };
  const exclude = (more: string[]) => setList((c) => c.filter((t) => !more.includes(t)));
  const share = () => { const u = new URL(featureHref("sc01"), location.origin); u.searchParams.set("s", encodeSettings({ universe: list.join(","), max_symbols: Math.max(list.length, 25) })); void navigator.clipboard?.writeText(u.toString()).then(() => toast.success("Link copied")); };

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
            <h4>Rank by</h4>
            <div className="ub-sizes">{BASIS.map(([k, l]) => <button key={k} type="button" aria-pressed={basis === k} onClick={() => onPatch({ rank_by: k })}>{l}</button>)}</div>
            <label className="ub-check"><input type="checkbox" checked={primary} onChange={(e) => onPatch({ primary_only: e.target.checked })} />Primary listing only</label>
            <h4>Presets</h4>
            <div className="ub-sizes">{PRESETS.map(([l, f]) => { const on = active(f); return <button key={l} type="button" aria-pressed={on} onClick={() => onPatch(on ? Object.fromEntries(Object.keys(f).map((k) => [k, k === "country" ? "all" : ""])) : f)}>{l}</button>; })}</div>
            <h4>Saved</h4>
            <div className="ub-saved">
              {(saved.data?.universes ?? []).map((u) => (
                <div key={u.universe_id} className="ub-saved-row">
                  <button type="button" onClick={() => merge(u.symbols)}>{u.name}<em>{u.count}</em></button>
                  <button type="button" className="ub-ic" aria-label={`Rename ${u.name}`} onClick={() => rename(u)}><Pencil size={12} /></button>
                  <button type="button" className="ub-ic" aria-label={`Delete ${u.name}`} onClick={() => remove(u)}><Trash2 size={12} /></button>
                </div>
              ))}
              {Object.entries(lists).filter(([, l]) => l.length).map(([id, l]) => <button key={id} type="button" onClick={() => merge(l)}>{id}<em>{l.length}</em></button>)}
            </div>
            <h4>Paste</h4>
            <input type="file" accept=".csv,text/csv" aria-label="Upload CSV" onChange={(e) => { const f = e.target.files?.[0]; if (!f) return; const body = new FormData(); body.append("file", f); void fetch(`${lab().base}/uploads`, { method: "POST", body }).then((r) => r.json()).then((j: { symbols?: string[]; detail?: string }) => { if (j.symbols) merge(j.symbols); else setErr(typeof j.detail === "string" ? j.detail : "Upload failed"); }).catch(() => setErr("Upload failed")); e.target.value = ""; }} />
            {err ? <small role="alert">{err}</small> : null}
            <textarea className="input" rows={2} placeholder="AAPL, MSFT" onBlur={(e) => { const v = e.target.value.toUpperCase().split(/[,;\s]+/).filter(Boolean); if (v.length) { merge(v); e.target.value = ""; } }} />
            {list.length ? (
              <>
                <h4>Exclude</h4>
                <textarea className="input" rows={1} placeholder="TSLA" aria-label="Exclude tickers" onBlur={(e) => { const v = e.target.value.toUpperCase().split(/[,;\s]+/).filter(Boolean); if (v.length) { exclude(v); e.target.value = ""; } }} />
                <h4>Chosen <em className={full ? "ub-full" : undefined}>{list.length.toLocaleString()}/{CAP.toLocaleString()}{full ? " · full" : ""}</em></h4>
                <div className="ub-chips">{list.slice(0, 80).map((t) => <button key={t} type="button" onClick={() => toggle(t)}>{t}<X size={11} /></button>)}</div>
                <div className="ub-save"><input className="input" placeholder="Name" value={saving} onChange={(e) => setSaving(e.target.value)} /><button type="button" className="btn sm" disabled={!saving.trim()} onClick={save}>Save</button></div>
              </>
            ) : null}
          </aside>
        </div>
        <footer className="ub-foot">
          <span>{list.length ? `${list.length} stocks` : `Top ${n.toLocaleString()} by liquidity`}</span>
          {list.length ? <button type="button" className="btn ghost" onClick={share}><Link2 size={13} />Share</button> : null}
          {list.length ? <button type="button" className="btn ghost" onClick={() => setList([])}>Clear</button> : null}
          <button type="button" className="btn primary" onClick={() => onApply(list, n)}>Use universe</button>
        </footer>
      </div>
    </div>
  );
}
