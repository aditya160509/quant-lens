"use client";

import { useQuery } from "@tanstack/react-query";
import type { FeatureSpec } from "@/modules/research/types";
import { studio } from "../api";
import type { QuickRun } from "../build/DevIDE";
import { RunSummary } from "../build/RunSummary";

type Snap = { name: string; version: number; files: Record<string, string>; run: QuickRun | null };

/** Read-only snapshot of one strategy version with its pinned run (DEV_IDEAS 19). */
export default function SharePage({ id }: { features: FeatureSpec[]; id?: string }) {
  const snap = useQuery({ queryKey: ["studio", "share", id], enabled: !!id, queryFn: () => studio<Snap>("GET", `/share/${id}`), retry: false });
  const s = snap.data;
  if (!s) return <div className="sh"><p className={snap.error ? "bd-find error" : "dv-empty"}>{snap.error ? (snap.error as Error).message : "Loading"}</p></div>;
  return (
    <div className="sh">
      <header className="sh-hd"><h1>{s.name}<small>v{s.version}</small></h1></header>
      {s.run?.status === "completed" ? <RunSummary quick={s.run} /> : null}
      {Object.entries(s.files).map(([name, text]) => <section key={name} className="sh-file"><h2>{name}</h2><pre>{text}</pre></section>)}
    </div>
  );
}
