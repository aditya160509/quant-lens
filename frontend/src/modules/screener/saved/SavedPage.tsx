"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Play, Save } from "lucide-react";
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
  const list = screens.data?.screens ?? [];
  return (
    <div style={{ display: "grid", gap: 12, padding: 16 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <button type="button" className="btn sm primary" onClick={() => save("01")}><Save size={12} />Save current screen</button>
        <button type="button" className="btn sm" onClick={() => save("06")}><Save size={12} />Save current alerts</button>
      </div>
      {!list.length && !screens.isLoading ? <Empty text="No saved screens" /> : null}
      {list.map((s) => {
        const sch = schedules.data?.schedules.find((x) => x.screen_id === s.screen_id);
        return (
          <section key={s.screen_id} className="island" style={{ padding: 12, display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <button type="button" className="tk-link" aria-expanded={open === s.screen_id} onClick={() => setOpen(open === s.screen_id ? null : s.screen_id)}>{s.name}</button>
              <span className="stat-s">{sch?.enabled ? EVERY.find(([sec]) => sec === sch.interval_seconds)?.[1] ?? `${sch.interval_seconds}s` : "Not scheduled"}{sch?.error ? ` · ${sch.error}` : ""}</span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
                <button type="button" className="btn sm ghost" onClick={() => { useStudies.setState((st) => ({ forms: { ...st.forms, [`sc${s.feature_id}`]: s.payload } })); router.push("/screener/screen"); }}>Load</button>
                <button type="button" className="btn sm ghost" aria-label={`Run ${s.name} now`} onClick={() => void run(() => send("POST", `/screens/${s.screen_id}/jobs`))}><Play size={12} /></button>
                <button type="button" className="btn sm ghost" aria-label={`Rename ${s.name}`} onClick={() => { const name = window.prompt("Rename", s.name)?.trim(); if (name) void run(() => send("PUT", `/screens/${s.screen_id}`, { name, feature_id: s.feature_id, payload: s.payload })); }}>Rename</button>
                <button type="button" className="btn sm ghost" aria-label={`Duplicate ${s.name}`} onClick={() => void run(() => send("PUT", `/screens/s${Date.now().toString(36)}`, { name: `${s.name} copy`, feature_id: s.feature_id, payload: s.payload }))}><Copy size={12} /></button>
              </span>
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
