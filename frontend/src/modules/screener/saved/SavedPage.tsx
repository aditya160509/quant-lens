"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Play, Save, Search } from "lucide-react";
import "./saved.css";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DataTable, Empty } from "@/kit/DataTable";
import { get, useManifest } from "@/modules/research/api";
import { defaultsFor, toPayload } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec, Row } from "@/modules/research/types";
import { send } from "../api";

type Screen = { screen_id: string; name: string; feature_id: string; payload: Record<string, unknown> };
type Schedule = { screen_id: string; interval_seconds: number; enabled: number; error: string | null };
const EVERY = [[3600, "Hourly"], [86400, "Daily"], [604800, "Weekly"]] as const;
const KIND: Record<string, string> = { "01": "Screen", "02": "Formula", "03": "Composite", "04": "Strategies", "05": "Backtest", "06": "Alerts", "07": "Valuation", "08": "Changes" };
/** What a saved screen holds, as short pills: kind, universe, size and each active filter. */
function summary(s: { feature_id: string; payload: Record<string, unknown> }): string[] {
  const p = s.payload ?? {};
  const uni = String(p.universe ?? "master");
  const filters = Object.entries(p).filter(([k, v]) => /_(min|max|top)$/.test(k) && v !== "" && v !== null && v !== undefined).map(([k, v]) => `${k.replace(/_(min|max|top)$/, "").replace(/_/g, " ")} ${k.endsWith("_min") ? "≥" : k.endsWith("_max") ? "≤" : "top"} ${String(v)}`);
  return [KIND[s.feature_id] ?? s.feature_id, ["master", "all", ""].includes(uni.toLowerCase()) ? `Top ${String(p.max_symbols ?? 500)} by liquidity` : `${uni.split(/[,\s]+/).filter(Boolean).length} names`, ...(p.sector && p.sector !== "all" ? [String(p.sector)] : []), ...filters.slice(0, 5), ...(filters.length > 5 ? [`+${filters.length - 5} more`] : [])];
}
const fail = (e: unknown) => window.alert(e instanceof Error ? e.message : "Failed");

/** Saved screens: rename, duplicate, re-run on a schedule, deliver changes and alerts, read the history and the alert scoreboard. */
export default function SavedPage({ features }: { features: FeatureSpec[] }) {
  const router = useRouter();
  const qc = useQueryClient();
  const manifest = useManifest();
  const [open, setOpen] = useState<string | null>(null);
  const screens = useQuery({ queryKey: ["screener", "screens"], queryFn: () => get<{ screens: Screen[] }>("/screens"), retry: false });
  const schedules = useQuery({ queryKey: ["screener", "schedules"], queryFn: () => get<{ schedules: Schedule[] }>("/schedules"), retry: false });
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["screener", "screens"] }), qc.invalidateQueries({ queryKey: ["screener", "schedules"] })]);
  const run = (fn: () => Promise<unknown>) => fn().then(refresh).catch(fail);
  const save = (fid: string) => {
    const spec = (manifest.data ?? features).find((f) => f.id === `sc${fid}`);
    const name = window.prompt("Name this screen")?.trim();
    if (!spec || !name) return;
    void run(() => send("PUT", `/screens/s${Date.now().toString(36)}`, { name, feature_id: fid, payload: toPayload(spec, useStudies.getState().forms[`sc${fid}`] ?? defaultsFor(spec)) }));
  };
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"name" | "newest">("newest");
  const list = (screens.data?.screens ?? []).filter((s) => !q || s.name.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (sort === "name" ? a.name.localeCompare(b.name) : b.screen_id.localeCompare(a.screen_id)));
  return (
    <div className="sv">
      <div className="sv-bar">
        <label className="sv-q"><Search size={13} aria-hidden /><input placeholder="Search saved" aria-label="Search saved screens" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <select className="sv-sort" aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as "name" | "newest")}><option value="newest">Newest</option><option value="name">Name</option></select>
        <button type="button" className="btn sm primary" onClick={() => save("01")}><Save size={12} />Save current screen</button>
        <button type="button" className="btn sm" onClick={() => save("06")}><Save size={12} />Save current alerts</button>
      </div>
      {!list.length && !screens.isLoading ? <Empty text="No saved screens" /> : null}
      {list.map((s) => {
        const sch = schedules.data?.schedules.find((x) => x.screen_id === s.screen_id);
        return (
          <section key={s.screen_id} className="sv-card" data-open={open === s.screen_id}>
            <div className="sv-head">
              <button type="button" className="sv-name" aria-expanded={open === s.screen_id} onClick={() => setOpen(open === s.screen_id ? null : s.screen_id)}>{s.name}</button>
              <span className={`sv-sched${sch?.enabled ? " on" : ""}${sch?.error ? " err" : ""}`} title={sch?.error ?? undefined}>{sch?.enabled ? EVERY.find(([sec]) => sec === sch.interval_seconds)?.[1] ?? `${sch.interval_seconds}s` : "Manual"}</span>
            </div>
            <div className="sv-pills">{summary(s).map((t) => <span key={t}>{t}</span>)}</div>
            <div className="sv-actions">
                <button type="button" className="btn sm ghost" onClick={() => { useStudies.setState((st) => ({ forms: { ...st.forms, [`sc${s.feature_id}`]: s.payload } })); router.push("/screener/screen"); }}>Load</button>
                <button type="button" className="btn sm ghost" aria-label={`Run ${s.name} now`} onClick={() => void run(() => send("POST", `/screens/${s.screen_id}/jobs`))}><Play size={12} /></button>
                <button type="button" className="btn sm ghost" aria-label={`Rename ${s.name}`} onClick={() => { const name = window.prompt("Rename", s.name)?.trim(); if (name) void run(() => send("PUT", `/screens/${s.screen_id}`, { name, feature_id: s.feature_id, payload: s.payload })); }}>Rename</button>
                <button type="button" className="btn sm ghost" aria-label={`Duplicate ${s.name}`} onClick={() => void run(() => send("PUT", `/screens/s${Date.now().toString(36)}`, { name: `${s.name} copy`, feature_id: s.feature_id, payload: s.payload }))}><Copy size={12} /></button>
            </div>
            {open === s.screen_id ? <Detail screen={s} schedule={sch} onChange={refresh} /> : null}
          </section>
        );
      })}
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
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <select className="input" aria-label="Re-run" value={schedule?.enabled ? schedule.interval_seconds : 0} onChange={(e) => { const sec = Number(e.target.value); void send("PUT", `/screens/${id}/schedule`, { interval_seconds: sec || 86400, enabled: sec > 0 }).then(onChange).catch(fail); }}>
          <option value={0}>Not scheduled</option>
          {EVERY.map(([sec, name]) => <option key={sec} value={sec}>{name}</option>)}
        </select>
      </div>
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
