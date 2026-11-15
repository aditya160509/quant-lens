"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DataTable } from "@/kit/DataTable";
import { useSavedScreens } from "@/kit/QuickLookData";
import { get, post } from "@/modules/research/api";
import { useStudies } from "@/modules/research/store";
import type { Row } from "@/modules/research/types";
import { Globe2, KeyRound, Link2, MessageSquareText } from "lucide-react";
import toast from "react-hot-toast";
import { SCREENER_BASE } from "../base";
import "./more.css";

const ASSETS = [["crypto", "Crypto"], ["fx", "Forex"], ["futures", "Futures"], ["hourly", "Hourly indices"]] as const;
const send = (path: string, method: string) => fetch(`${SCREENER_BASE}${path}`, { method }).then((r) => { if (!r.ok) throw new Error(`Request failed (${r.status})`); });
const fail = (e: unknown) => (e instanceof Error ? <div role="alert" style={{ color: "var(--down)" }}>{e.message}</div> : null);

/** Price-only: these markets carry no fundamentals here. Pattern is a mechanical rule on closes, weak evidence of future returns. */
function Markets() {
  const [asset, setAsset] = useState<string>("crypto");
  const rows = useQuery({ queryKey: ["screener", "markets", asset], queryFn: () => get<{ rows: Row[] }>(`/markets/${asset}`), retry: false });
  const shown = (rows.data?.rows ?? []).map((r) => (asset === "hourly" ? r : { ...r, pattern_weak_evidence: r.pattern, pattern: undefined }));
  return (
    <section className="card more-c more-wide">
      <div className="card-h"><Globe2 size={14} /><h3>Markets</h3><span className="sub num">{rows.data ? `${shown.length} names, price only` : ""}</span>
        <div className="ub-seg more-seg" role="radiogroup" aria-label="Market">{ASSETS.map(([id, name]) => <button key={id} type="button" role="radio" aria-checked={asset === id} onClick={() => setAsset(id)}>{name}</button>)}</div>
      </div>
      <div className="card-b flush">{rows.isError ? fail(rows.error) : rows.isLoading ? <div className="more-skel skel-card" aria-busy="true" /> : <DataTable rows={shown} opts={{ hide: ["pattern"] }} />}</div>
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
    <section className="card more-c">
      <div className="card-h"><MessageSquareText size={14} /><h3>Plain English to formula</h3></div>
      <div className="card-b more-b">
      <div className="more-row">
        <input className="input" aria-label="Describe the screen" placeholder="Cheap profitable large caps with rising sales" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && text.trim() && ask.mutate()} />
        <button className="btn primary" disabled={!text.trim() || ask.isPending} onClick={() => ask.mutate()}>Write formula</button>
      </div>
      {fail(ask.error)}
      {formula ? <>
        <textarea className="input" aria-label="Formula" value={formula} onChange={(e) => setFormula(e.target.value)} rows={2} style={{ width: "100%" }} />
        {unmatched.length ? <div className="more-note">No rule for: {unmatched.join(", ")}</div> : null}
        <button className="btn" onClick={use}>Use in Formula</button>
      </> : null}
      </div>
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
  const url = (t: string) => `${window.location.origin}/share/${t}`;
  const named = new Map((screens.data?.screens ?? []).map((s) => [s.screen_id, s.name]));
  const linked = new Set((shares.data?.shares ?? []).map((s) => s.screen_id));
  const copy = (text: string, what: string) => void navigator.clipboard.writeText(text).then(() => toast.success(`${what} copied`));
  return (
    <>
    <section className="card more-c">
      <div className="card-h"><Link2 size={14} /><h3>Share links</h3><span className="sub num">{shares.data?.shares.length ?? 0}</span></div>
      <div className="card-b more-b">
      {(shares.data?.shares ?? []).map((s) => (
        <div key={s.token} className="kv-row">
          <a href={url(s.token)} target="_blank" rel="noreferrer">{named.get(s.screen_id) ?? s.screen_id}</a>
          <span className="more-acts">
            <button className="btn sm ghost" onClick={() => copy(url(s.token), "Link")}>Copy link</button>
            <button className="btn sm ghost" onClick={() => copy(`<iframe src="${url(s.token)}?embed=1" width="100%" height="600" style="border:0"></iframe>`, "Embed code")}>Embed</button>
            <button className="btn sm ghost" onClick={() => unshare.mutate(s.token)}>Revoke</button>
          </span>
        </div>
      ))}
      {(screens.data?.screens ?? []).filter((s) => !linked.has(s.screen_id)).map((s) => <div key={s.screen_id} className="kv-row"><span>{s.name}</span><button className="btn sm" onClick={() => share.mutate(s.screen_id)}>Create link</button></div>)}
      {!screens.data?.screens.length ? <p className="more-note">Save a screen to share it.</p> : null}
      {fail(share.error ?? unshare.error)}
      </div>
    </section>
    <section className="card more-c">
      <div className="card-h"><KeyRound size={14} /><h3>API keys</h3><span className="sub num">{keys.data?.keys.length ?? 0}</span></div>
      <div className="card-b more-b">
      <div className="more-row">
        <input className="input" aria-label="Key name" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input more-limit" aria-label="Requests per day" type="number" min={1} value={limit} onChange={(e) => setLimit(e.target.value)} />
        <button className="btn primary" disabled={!name.trim() || !(Number(limit) >= 1)} onClick={() => make.mutate()}>Create key</button>
      </div>
      {fresh ? <button type="button" className="more-key" onClick={() => copy(fresh, "Key")}><code>{fresh}</code><span>Copy</span></button> : null}
      {fail(make.error ?? revoke.error)}
      {(keys.data?.keys ?? []).map((k) => <div key={k.id} className="kv-row"><span>{k.name}</span><span className="num more-use">{k.used_today.toLocaleString()} of {k.daily_limit.toLocaleString()} today</span><button className="btn sm ghost" onClick={() => revoke.mutate(k.id)}>Revoke</button></div>)}
      </div>
    </section>
    </>
  );
}

export default function MorePage(_props: { features: unknown[]; id?: string }) {
  return <div className="more"><Markets /><EnglishFormula /><SharingAndKeys /></div>;
}
