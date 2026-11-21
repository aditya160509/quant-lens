"use client";

import { Link2, Printer, Share2 } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import toast from "react-hot-toast";
import { DataTable } from "@/kit/DataTable";
import type { FeatureSpec } from "@/modules/research/types";
import { studio, useHome } from "../api";
import type { QuickRun } from "../build/DevIDE";
import { DevRobust } from "../build/DevRobust";
import { DevTearsheet } from "../build/DevTearsheet";
import { RunSummary } from "../build/RunSummary";

const TABS = ["Summary", "Tearsheet", "Robustness", "Trades", "Certificate"] as const;
type Cert = { match: boolean; run_hash: string; result_hash: string; reproduced_hash: string; data_version: string; grade: string | null; headline: string | null };

/** Report (W-11): one finished run on its own page, to read, print or share. Without a run id it lists recent runs. */
export default function ReportPage({ id }: { features: FeatureSpec[]; id?: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Summary");
  const [cert, setCert] = useState<Cert | "loading" | null>(null);
  const run = useQuery({ queryKey: ["studio", "report", id], enabled: !!id, queryFn: () => studio<QuickRun>("GET", `/jobs/${id}`), retry: 1 });
  const home = useHome();
  if (!id) {
    const runs = home.data?.recent_runs ?? [];
    return (
      <div className="rp">
        <header className="rp-hd"><h1>Reports</h1></header>
        {runs.length ? <div className="rp-list">{runs.map((r) => (
          <Link key={r.job_id} href={`/studio/report/${r.job_id}`}><b>{r.strategy ?? "Untitled"}{r.version ? ` v${r.version}` : ""}</b><span>{r.headline}</span><time>{new Date(r.at * 1000).toLocaleString()}</time></Link>
        ))}</div> : <p className="dv-empty">{home.isLoading ? "Loading" : "No runs yet"}</p>}
      </div>
    );
  }
  const q = run.data ?? null;
  const meta = q?.result?.meta as { strategy?: { id?: string; name?: string; version?: number | null } } | undefined;
  const name = meta?.strategy?.name ?? "Run";
  const reproduce = () => { setCert("loading"); void studio<Cert>("POST", `/jobs/${id}/reproduce`).then(setCert, (e: Error) => { setCert(null); toast.error(e.message); }); };
  return (
    <div className="rp">
      <header className="rp-hd">
        <h1>{name}{meta?.strategy?.version ? <small>v{meta.strategy.version}</small> : null}</h1>
        <div className="rp-tabs" role="tablist">{TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}</div>
        <span className="rp-act">
          {meta?.strategy?.id ? <Link className="btn sm ghost" href={`/studio/build/${meta.strategy.id}?ui=dev`}>Open in Build</Link> : null}
          <button className="btn sm ghost" aria-label="Copy link" title="Copy link" onClick={() => void navigator.clipboard.writeText(location.href).then(() => toast.success("Link copied"))}><Link2 size={14} /></button>
          {meta?.strategy?.id ? <button className="btn sm ghost" aria-label="Share link" title="Share link" onClick={() => void studio<{ token: string }>("POST", `/strategies/${meta.strategy?.id}/share?${new URLSearchParams({ job_id: id, ...(meta.strategy?.version ? { version: String(meta.strategy.version) } : {}) })}`).then((r) => navigator.clipboard.writeText(`${location.origin}/studio/share/${r.token}`)).then(() => toast.success("Share link copied"), (e: Error) => toast.error(e.message))}><Share2 size={14} /></button> : null}
          <button className="btn sm ghost" aria-label="Print or save as PDF" title="Print or save as PDF" onClick={() => window.print()}><Printer size={14} /></button>
        </span>
      </header>
      {run.isLoading ? <p className="dv-empty">Loading</p> : run.error ? <p className="bd-find error"><b>Not found</b>{(run.error as Error).message}</p> : q?.status !== "completed" ? <p className="dv-empty">This run is {q?.status ?? "unknown"}</p> : (
        <div className="rp-body">
          {tab === "Summary" ? <RunSummary quick={q} /> : null}
          {tab === "Tearsheet" ? <DevTearsheet quick={q} /> : null}
          {tab === "Robustness" ? <DevRobust quick={q} /> : null}
          {tab === "Trades" ? (q.result?.tables?.trades?.length ? <DataTable rows={q.result.tables.trades} opts={{ viewKey: "studio:report:trades" }} /> : <p className="dv-empty">No trades</p>) : null}
          {tab === "Certificate" ? (
            <div className="rp-cert">
              <p>Re-run this job on the server from its stored settings and compare the result hash.</p>
              <button className="btn sm" disabled={cert === "loading"} onClick={reproduce}>{cert === "loading" ? "Reproducing…" : "Reproduce"}</button>
              {cert && cert !== "loading" ? (
                <dl className="dv-kv">
                  <div><dt>Result</dt><dd className={cert.match ? "st-up" : "error"}>{cert.match ? "Reproduced exactly" : "Hashes differ"}</dd></div>
                  <div><dt>Run hash</dt><dd>{cert.run_hash}</dd></div>
                  <div><dt>Result hash</dt><dd>{cert.result_hash}</dd></div>
                  <div><dt>Reproduced hash</dt><dd>{cert.reproduced_hash}</dd></div>
                  <div><dt>Data version</dt><dd>{cert.data_version}</dd></div>
                  {cert.grade ? <div><dt>Grade</dt><dd>{cert.grade}</dd></div> : null}
                </dl>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
