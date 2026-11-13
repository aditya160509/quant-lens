"use client";

import toast from "react-hot-toast";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Copy, FolderInput, Play, Save, Search, Tag } from "lucide-react";
import "./saved.css";
import "../filters/universe.css";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DataTable, Empty } from "@/kit/DataTable";
import { get, useManifest } from "@/modules/research/api";
import { defaultsFor, toPayload } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec, Row } from "@/modules/research/types";
import { send } from "../api";

type Screen = { screen_id: string; name: string; feature_id: string; payload: Record<string, unknown> };
type Schedule = { screen_id: string; interval_seconds: number; next_due: number; enabled: number; error: string | null };
type HistoryRun = { run_id: string; as_of_date: string; result: { summary_cards?: { label: string; value: unknown }[] } };
const EVERY = [[3600, "Hourly"], [86400, "Daily"], [604800, "Weekly"]] as const;
const KIND: Record<string, string> = { "01": "Screen", "02": "Formula", "03": "Composite", "04": "Strategies", "05": "Backtest", "06": "Alerts", "07": "Valuation", "08": "Changes" };
/** What a saved screen holds, as short pills: kind, universe, size and each active filter. */
function summary(s: { feature_id: string; payload: Record<string, unknown> }): string[] {
  const p = s.payload ?? {};
  const uni = String(p.universe ?? "master");
  const filters = Object.entries(p).filter(([k, v]) => /_(min|max|top)$/.test(k) && v !== "" && v !== null && v !== undefined).map(([k, v]) => `${k.replace(/_(min|max|top)$/, "").replace(/_/g, " ")} ${k.endsWith("_min") ? "≥" : k.endsWith("_max") ? "≤" : "top"} ${String(v)}`);
  return [KIND[s.feature_id] ?? s.feature_id, ["master", "all", ""].includes(uni.toLowerCase()) ? `Top ${String(p.max_symbols ?? 500)} by liquidity` : `${uni.split(/[,\s]+/).filter(Boolean).length} names`, ...(p.sector && p.sector !== "all" ? [String(p.sector)] : []), ...filters.slice(0, 5), ...(filters.length > 5 ? [`+${filters.length - 5} more`] : [])];
}
type Count = { count: number | null; reason: string | null };
type Change = { entrants: string[] | null; exits: string[] | null; reason: string | null };
const ARCH = "screener-archived-screens";
const readArch = (): string[] => { try { return JSON.parse(localStorage.getItem(ARCH) ?? "[]"); } catch { return []; } };
// Folders and tags live on this device, like archive: the screens API has no fields for them.
type Meta = Record<string, { folder?: string; tags?: string[] }>;
const META = "screener-screen-meta";
const readMeta = (): Meta => { try { return JSON.parse(localStorage.getItem(META) ?? "{}"); } catch { return {}; } };
const fail = (e: unknown) => toast.error(e instanceof Error ? e.message : "Failed");

/** Saved screens: rename, duplicate, re-run on a schedule, deliver changes and alerts, read the history and the alert scoreboard. */
export default function SavedPage({ features }: { features: FeatureSpec[] }) {
  const router = useRouter();
  const qc = useQueryClient();
  const manifest = useManifest();
  const [open, setOpen] = useState<string | null>(null);
  const screens = useQuery({ queryKey: ["screener", "screens"], queryFn: () => get<{ screens: Screen[] }>("/screens"), retry: false });
  const schedules = useQuery({ queryKey: ["screener", "schedules"], queryFn: () => get<{ schedules: Schedule[] }>("/schedules"), retry: false });
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["screener", "screens"] }), qc.invalidateQueries({ queryKey: ["screener", "schedules"] })]);
  const run = (fn: () => Promise<unknown>) => fn().then(refresh).then(() => toast.success("Saved")).catch(fail);
  const save = (fid: string) => {
    const spec = (manifest.data ?? features).find((f) => f.id === `sc${fid}`);
    const name = window.prompt("Name this screen")?.trim();
    if (!spec || !name) return;
    void run(() => send("PUT", `/screens/s${Date.now().toString(36)}`, { name, feature_id: fid, payload: toPayload(spec, useStudies.getState().forms[`sc${fid}`] ?? defaultsFor(spec)) }));
  };
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"name" | "newest" | "matches">("newest");
  const [arch, setArch] = useState<string[]>([]);
  const [showArch, setShowArch] = useState(false);
  const [meta, setMeta] = useState<Meta>({});
  const [folder, setFolder] = useState<string | null>(null);
  useEffect(() => { setArch(readArch()); setMeta(readMeta()); }, []);
  const patchMeta = (id: string, p: Meta[string]) => { const next = { ...meta, [id]: { ...meta[id], ...p } }; setMeta(next); try { localStorage.setItem(META, JSON.stringify(next)); } catch { /* storage blocked */ } };
  const all = (screens.data?.screens ?? []).filter((s) => arch.includes(s.screen_id) === showArch);
  const folders = [...new Set(all.map((s) => meta[s.screen_id]?.folder).filter((f): f is string => !!f))].sort();
  const toggleArch = (id: string) => { const next = arch.includes(id) ? arch.filter((x) => x !== id) : [...arch, id]; setArch(next); try { localStorage.setItem(ARCH, JSON.stringify(next)); } catch { /* storage blocked */ } };
  const ids = (screens.data?.screens ?? []).map((s) => s.screen_id);
  const counts = useQuery({ queryKey: ["screener", "counts", ids.join(",")], queryFn: () => get<{ counts: Record<string, Count> }>("/screens/counts"), enabled: ids.length > 0, staleTime: 300_000, retry: false }).data?.counts;
  const changes = useQuery({ queryKey: ["screener", "changes", ids.join(",")], queryFn: () => get<{ changes: Record<string, Change> }>(`/screens/changes?ids=${ids.slice(0, 50).join(",")}`), enabled: ids.length > 0, staleTime: 300_000, retry: false }).data?.changes;
  const list = all.filter((s) => !folder || meta[s.screen_id]?.folder === folder).filter((s) => !q || `${s.name} ${(meta[s.screen_id]?.tags ?? []).join(" ")}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (sort === "name" ? a.name.localeCompare(b.name) : sort === "matches" ? (counts?.[b.screen_id]?.count ?? -1) - (counts?.[a.screen_id]?.count ?? -1) : b.screen_id.localeCompare(a.screen_id)));
  return (
    <div className="sv">
      <div className="sv-bar">
        <label className="sv-q"><Search size={13} aria-hidden /><input placeholder="Search saved" aria-label="Search saved screens" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <select className="sv-sort" aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as "name" | "newest" | "matches")}><option value="newest">Newest</option><option value="name">Name</option><option value="matches">Matches</option></select>
        <button type="button" className="btn sm ghost" aria-pressed={showArch} onClick={() => setShowArch(!showArch)}><Archive size={12} />Archived{arch.length ? ` ${arch.length}` : ""}</button>
        <button type="button" className="btn sm primary" onClick={() => save("01")}><Save size={12} />Save current screen</button>
        <button type="button" className="btn sm" onClick={() => save("06")}><Save size={12} />Save current alerts</button>
      </div>
      {folders.length ? (
        <div className="sv-folders" role="group" aria-label="Folders">
          {[null, ...folders].map((f) => {
            const n = all.filter((s) => !f || meta[s.screen_id]?.folder === f).length;
            return <button key={f ?? "all"} type="button" className="sv-folder" aria-pressed={folder === f} onClick={() => setFolder(f)}><i aria-hidden /><span>{f ?? "All screens"}</span><b className="num">{n}</b></button>;
          })}
        </div>
      ) : null}
      {screens.isLoading ? [0, 1, 2].map((i) => <div key={i} className="skel-card" style={{ height: 120 }} aria-busy="true" />) : null}
      {!list.length && !screens.isLoading ? <Empty text={showArch ? "No archived screens" : "No saved screens"} /> : null}
      {list.map((s) => {
        const sch = schedules.data?.schedules.find((x) => x.screen_id === s.screen_id);
        return (
          <section key={s.screen_id} className="sv-card" data-open={open === s.screen_id}>
            <div className="sv-head">
              <button type="button" className="sv-name" aria-expanded={open === s.screen_id} onClick={() => setOpen(open === s.screen_id ? null : s.screen_id)}>{s.name}</button>
              <span className={`sv-sched${sch?.enabled ? " on" : ""}${sch?.error ? " err" : ""}`} title={sch?.error ?? undefined}>{sch?.enabled ? EVERY.find(([sec]) => sec === sch.interval_seconds)?.[1] ?? `${sch.interval_seconds}s` : "Manual"}</span>
            </div>
            <Mini id={s.screen_id} count={counts?.[s.screen_id]} change={changes?.[s.screen_id]} />
            <div className="sv-pills">{(meta[s.screen_id]?.tags ?? []).map((t) => <span key={`#${t}`} className="sv-tag">#{t}</span>)}{summary(s).map((t) => <span key={t}>{t}</span>)}</div>
            <div className="sv-actions">
                <button type="button" className="btn sm ghost" onClick={() => { useStudies.setState((st) => ({ forms: { ...st.forms, [`sc${s.feature_id}`]: s.payload } })); router.push("/screener/screen"); }}>Load</button>
                <button type="button" className="btn sm ghost" aria-label={`Run ${s.name} now`} onClick={() => void run(() => send("POST", `/screens/${s.screen_id}/jobs`))}><Play size={12} /></button>
                <button type="button" className="btn sm ghost" aria-label={`Rename ${s.name}`} onClick={() => { const name = window.prompt("Rename", s.name)?.trim(); if (name) void run(() => send("PUT", `/screens/${s.screen_id}`, { name, feature_id: s.feature_id, payload: s.payload })); }}>Rename</button>
                <button type="button" className="btn sm ghost" aria-label={`Duplicate ${s.name}`} onClick={() => void run(() => send("PUT", `/screens/s${Date.now().toString(36)}`, { name: `${s.name} copy`, feature_id: s.feature_id, payload: s.payload }))}><Copy size={12} /></button>
                <button type="button" className="btn sm ghost" aria-label={`Move ${s.name} to a folder`} onClick={() => { const f = window.prompt("Folder (empty to remove)", meta[s.screen_id]?.folder ?? ""); if (f !== null) patchMeta(s.screen_id, { folder: f.trim() || undefined }); }}><FolderInput size={12} /></button>
                <button type="button" className="btn sm ghost" aria-label={`Tag ${s.name}`} onClick={() => { const t = window.prompt("Tags, comma separated", (meta[s.screen_id]?.tags ?? []).join(", ")); if (t !== null) patchMeta(s.screen_id, { tags: t.split(",").map((x) => x.trim().replace(/^#/, "")).filter(Boolean) }); }}><Tag size={12} /></button>
                <button type="button" className="btn sm ghost" aria-label={`${arch.includes(s.screen_id) ? "Restore" : "Archive"} ${s.name}`} onClick={() => toggleArch(s.screen_id)}>{arch.includes(s.screen_id) ? <ArchiveRestore size={12} /> : <Archive size={12} />}</button>
            </div>
            {open === s.screen_id ? <Detail screen={s} schedule={sch} onChange={refresh} /> : null}
          </section>
        );
      })}
    </div>
  );
}

/** Live match count, names in and out since the previous run, and when it last ran. */
function Mini({ id, count, change }: { id: string; count?: Count; change?: Change }) {
  const last = useQuery({ queryKey: ["screener", "history", id, 1], queryFn: () => get<{ runs: HistoryRun[] }>(`/screens/${id}/history?limit=1`), retry: false }).data?.runs[0];
  const n = change?.entrants?.length ?? 0, x = change?.exits?.length ?? 0;
  return (
    <div className="sv-mini">
      <b className="num" title={count?.reason ?? undefined}>{count?.count?.toLocaleString() ?? "–"}</b>
      {change?.entrants ? <span className="num" title={[...change.entrants.map((t) => `+${t}`), ...(change.exits ?? []).map((t) => `−${t}`)].join(" ")}><em className="up">+{n}</em> <em className="down">−{x}</em></span> : null}
      {last ? <span className="num sv-last">{last.as_of_date}</span> : null}
    </div>
  );
}

/** Off, hourly, daily, weekly or every N hours; shows when it runs next and the last error. */
function SchedulePicker({ id, schedule, onChange }: { id: string; schedule?: Schedule; onChange: () => Promise<unknown> }) {
  const on = Boolean(schedule?.enabled);
  const sec = on ? schedule!.interval_seconds : 0;
  const custom = on && !EVERY.some(([s]) => s === sec);
  const put = (interval: number, enabled: boolean) => void send("PUT", `/screens/${id}/schedule`, { interval_seconds: interval, enabled }).then(onChange).catch(fail);
  return (
    <div className="sv-sched">
      <div className="ub-seg" role="radiogroup" aria-label="Re-run">
        <button type="button" role="radio" aria-checked={!on} onClick={() => put(schedule?.interval_seconds || 86400, false)}>Off</button>
        {EVERY.map(([s, name]) => <button key={s} type="button" role="radio" aria-checked={on && sec === s} onClick={() => put(s, true)}>{name}</button>)}
      </div>
      <label className="sv-every">Every<input className="input num" type="number" min={1} max={168} aria-label="Every N hours" key={sec} defaultValue={custom ? Math.round(sec / 3600) : ""} placeholder="N" onBlur={(e) => { const h = Number(e.target.value); if (h >= 1 && h <= 168 && h * 3600 !== sec) put(h * 3600, true); }} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} />hours</label>
      {on && schedule?.next_due ? <span className="stat-s num">Next {new Date(schedule.next_due * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span> : null}
      {schedule?.error ? <span className="sh-pill red" title={schedule.error}>Last run failed</span> : null}
    </div>
  );
}

/** One bar per stored run, height by names passing; hover for the date and count. */
function RunTimeline({ id }: { id: string }) {
  const runs = useQuery({ queryKey: ["screener", "history", id], queryFn: () => get<{ runs: HistoryRun[] }>(`/screens/${id}/history?limit=40`), retry: false }).data?.runs ?? [];
  const points = runs.map((r) => ({ date: r.as_of_date, n: Number(r.result.summary_cards?.find((c) => c.label === "After filters")?.value ?? NaN) })).filter((x) => Number.isFinite(x.n)).reverse();
  if (points.length < 2) return null;
  const top = Math.max(1, ...points.map((x) => x.n));
  return (
    <div className="sv-tl" role="img" aria-label={`Names passing over ${points.length} runs, from ${points[0].n} to ${points.at(-1)!.n}`}>
      {points.map((x, i) => <i key={`${x.date}-${i}`} title={`${x.date}: ${x.n}`} style={{ height: `${Math.max(6, (x.n / top) * 100)}%` }} />)}
      <span className="num">{points[0].date}</span><span className="num">{points.at(-1)!.date}</span>
    </div>
  );
}

function Detail({ screen, schedule, onChange }: { screen: Screen; schedule?: Schedule; onChange: () => Promise<unknown> }) {
  const id = screen.screen_id;
  const [url, setUrl] = useState("");
  const [digest, setDigest] = useState(false);
  const channels = useQuery({ queryKey: ["screener", "channels", id], queryFn: () => get<{ channels: { service: string; digest: boolean }[] }>(`/screens/${id}/channels`), retry: false });
  const events = useQuery({ queryKey: ["screener", "events", id], queryFn: () => get<{ events: Row[] }>(`/screens/${id}/events`), retry: false });
  const precision = useQuery({ queryKey: ["screener", "precision", id], queryFn: () => get<{ precision: Row[] }>(`/screens/${id}/precision`), retry: false });
  const services = (channels.data?.channels ?? []).map((c) => c.service);
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <SchedulePicker id={id} schedule={schedule} onChange={onChange} />
      <RunTimeline id={id} />
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" style={{ flex: 1, minWidth: 220 }} type="password" autoComplete="off" aria-label="Apprise URL" placeholder="mailto://, tgram://, ntfy://, json://" value={url} onChange={(e) => setUrl(e.target.value)} />
        <label style={{ fontSize: 12 }}><input type="checkbox" checked={digest} onChange={(e) => setDigest(e.target.checked)} /> Digest</label>
        <button type="button" className="btn sm" disabled={!url.trim()} onClick={() => void send("PUT", `/screens/${id}/channels`, { urls: [url], digest }).then(() => { setUrl(""); return channels.refetch(); }).catch(fail)}>Deliver here</button>
        {services.length ? <span className="stat-s">{services.join(", ")}</span> : null}
      </div>
      <h4>History</h4>
      {events.data?.events.length ? <DataTable rows={events.data.events} opts={{ max: 200, maxHeight: 280 }} /> : <Empty text="No changes yet" />}
      <h4>Delivered alerts</h4>
      {precision.data?.precision.length ? <DataTable rows={precision.data.precision} opts={{ max: 50, maxHeight: 240 }} /> : <Empty text="None matured yet" />}
    </div>
  );
}
