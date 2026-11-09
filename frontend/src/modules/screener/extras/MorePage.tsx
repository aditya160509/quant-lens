"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DataTable } from "@/kit/DataTable";
import { useSavedScreens } from "@/kit/QuickLookData";
import { get, post } from "@/modules/research/api";
import { useStudies } from "@/modules/research/store";
import type { Row } from "@/modules/research/types";
import { SCREENER_BASE } from "../base";

const ASSETS = [["crypto", "Crypto"], ["fx", "Forex"], ["futures", "Futures"], ["hourly", "Hourly indices"]] as const;
const send = (path: string, method: string) => fetch(`${SCREENER_BASE}${path}`, { method }).then((r) => { if (!r.ok) throw new Error(`Request failed (${r.status})`); });
const fail = (e: unknown) => (e instanceof Error ? <div role="alert" style={{ color: "var(--down)" }}>{e.message}</div> : null);

/** Price-only: these markets carry no fundamentals here. Pattern is a mechanical rule on closes, weak evidence of future returns. */
function Markets() {
  const [asset, setAsset] = useState<string>("crypto");
  const rows = useQuery({ queryKey: ["screener", "markets", asset], queryFn: () => get<{ rows: Row[] }>(`/markets/${asset}`), retry: false });
  const shown = (rows.data?.rows ?? []).map((r) => (asset === "hourly" ? r : { ...r, pattern_weak_evidence: r.pattern, pattern: undefined }));
  return (
    <section>
      <h2>Markets, price only</h2>
      <div role="tablist">{ASSETS.map(([id, name]) => <button key={id} role="tab" aria-selected={asset === id} className="chip" onClick={() => setAsset(id)}>{name}</button>)}</div>
      {rows.isError ? fail(rows.error) : rows.isLoading ? <div aria-busy="true" /> : <DataTable rows={shown} opts={{ hide: ["pattern"] }} />}
    </section>
  );
}

/** Rule-based: unmatched words are listed, never guessed. The formula stays editable and goes to the Formula page. */
function EnglishFormula() {
  const [text, setText] = useState("");
  const [formula, setFormula] = useState("");
  const [unmatched, setUnmatched] = useState<string[]>([]);
  const ask = useMutation({
    mutationFn: () => post<{ formula: string; unmatched: string[] }>("/nl-formula", { text }),
    onSuccess: (r) => { setFormula(r.formula); setUnmatched(r.unmatched); },
  });
  const use = () => useStudies.setState((s) => ({ forms: { ...s.forms, sc02: { ...(s.forms.sc02 ?? {}), formula } } }));
  return (
    <section>
      <h2>Plain English to formula</h2>
      <input className="input" aria-label="Describe the screen" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && text.trim() && ask.mutate()} />
      <button className="btn" disabled={!text.trim() || ask.isPending} onClick={() => ask.mutate()}>Write formula</button>
      {fail(ask.error)}
      {formula ? <>
        <textarea className="input" aria-label="Formula" value={formula} onChange={(e) => setFormula(e.target.value)} rows={2} style={{ width: "100%" }} />
        {unmatched.length ? <div>No rule for: {unmatched.join(", ")}</div> : null}
        <button className="btn" onClick={use}>Use in Formula</button>
      </> : null}
    </section>
  );
}

type Share = { token: string; screen_id: string; created: string };
type Key = { id: string; name: string; daily_limit: number; used_today: number; created: string };

/** Share links are public and unauthenticated; a key's full value is shown once. */
function SharingAndKeys() {
  const qc = useQueryClient();
  const screens = useSavedScreens();
  const shares = useQuery({ queryKey: ["screener", "shares"], queryFn: () => get<{ shares: Share[] }>("/shares"), retry: false });
  const keys = useQuery({ queryKey: ["screener", "keys"], queryFn: () => get<{ keys: Key[] }>("/api-keys"), retry: false });
  const [name, setName] = useState("");
  const [limit, setLimit] = useState("1000");
  const [fresh, setFresh] = useState<string | null>(null);
  const refresh = (k: string) => qc.invalidateQueries({ queryKey: ["screener", k] });
  const share = useMutation({ mutationFn: (id: string) => post<{ token: string }>(`/screens/${encodeURIComponent(id)}/share`, {}), onSuccess: () => refresh("shares") });
  const unshare = useMutation({ mutationFn: (t: string) => send(`/shares/${t}`, "DELETE"), onSuccess: () => refresh("shares") });
  const make = useMutation({ mutationFn: () => post<{ key: string }>("/api-keys", { name, daily_limit: Number(limit) }), onSuccess: (r) => { setFresh(r.key); setName(""); refresh("keys"); } });
  const revoke = useMutation({ mutationFn: (id: string) => send(`/api-keys/${id}`, "DELETE"), onSuccess: () => refresh("keys") });
  const url = (t: string) => `${SCREENER_BASE}/shared/${t}`;
  return (
    <section>
      <h2>Share links</h2>
      {(screens.data?.screens ?? []).map((s) => <div key={s.screen_id} className="kv-row"><span>{s.name}</span><button className="btn" onClick={() => share.mutate(s.screen_id)}>Create link</button></div>)}
      {(shares.data?.shares ?? []).map((s) => <div key={s.token} className="kv-row"><a href={url(s.token)} target="_blank" rel="noreferrer">{url(s.token)}</a><button className="btn" onClick={() => unshare.mutate(s.token)}>Revoke</button></div>)}
      {fail(share.error ?? unshare.error)}
      <h2>API keys</h2>
      <input className="input" aria-label="Key name" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
      <input className="input" aria-label="Requests per day" type="number" min={1} value={limit} onChange={(e) => setLimit(e.target.value)} />
      <button className="btn" disabled={!name.trim() || !(Number(limit) >= 1)} onClick={() => make.mutate()}>Create key</button>
      {fresh ? <div><code>{fresh}</code></div> : null}
      {fail(make.error ?? revoke.error)}
      {(keys.data?.keys ?? []).map((k) => <div key={k.id} className="kv-row"><span>{k.name}</span><span className="num">{k.used_today.toLocaleString()} of {k.daily_limit.toLocaleString()} today</span><button className="btn" onClick={() => revoke.mutate(k.id)}>Revoke</button></div>)}
    </section>
  );
}

export default function MorePage(_props: { features: unknown[]; id?: string }) {
  return <div style={{ display: "grid", gap: 32 }}><Markets /><EnglishFormula /><SharingAndKeys /></div>;
}
