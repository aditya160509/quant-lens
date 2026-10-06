"use client";

import { ArrowRight, Check, Circle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRuns } from "@/modules/research/api";
import { featureHref, metaFor } from "@/modules/research/catalog";
import type { FeatureSpec, RunRecord } from "@/modules/research/types";

/** The thin strategy studio: the four pages as one pipeline, each step showing its latest run and where it hands off. */
const STEPS: { id: string; step: string; does: string; next?: string }[] = [
  { id: "ml02", step: "Signal", does: "Rank names by expected 21-day return with LightGBM and Ridge, or bring your own features.", next: "Hand the held-out predictions to the filter, the allocation or Validate." },
  { id: "ml04", step: "Filter", does: "Label trades by which barrier they hit first and let a second model skip or shrink the weak ones.", next: "Compare filtered against unfiltered before keeping it." },
  { id: "ml03", step: "Size", does: "Scale exposure to a volatility target or half-Kelly, always beside unmanaged.", next: "Use the market-state regimes to switch models in stress." },
  { id: "ml05", step: "Allocate", does: "Shrinkage minimum variance with alpha views, net of costs, with a trade list for your holdings.", next: "Hand the walk-forward returns to Validate." },
  { id: "mlvalidate", step: "Validate", does: "Controls, shuffled signals, bootstrap, transfer and the overfitting autopsy decide whether it holds up.", next: "Publish a verified page when it does." },
];

const TONE: Record<string, string> = { up: "var(--up)", warn: "var(--warn)", down: "var(--down)" };

function Status({ run }: { run?: RunRecord }) {
  if (!run) return <span className="studio-status" data-s="none"><Circle size={12} />Not run yet</span>;
  if (run.status === "running" || run.status === "queued") return <span className="studio-status" data-s="run"><Loader2 size={12} className="spin" />Running</span>;
  if (run.status !== "completed") return <span className="studio-status" data-s="fail"><Circle size={12} />{run.status}</span>;
  return <span className="studio-status" data-s="done" style={{ color: TONE[run.tone ?? ""] ?? "var(--up)" }}><Check size={12} />{new Date(run.startedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>;
}

export function StudioPage({ features }: { features: FeatureSpec[] }) {
  const runs = useRuns((s) => s.runs);
  const have = new Set(features.map((f) => f.id));
  const latest = (id: string) => runs.find((r) => r.featureId === id);
  const done = STEPS.filter((s) => latest(s.id)?.status === "completed").length;
  return (
    <div className="studio">
      <header className="studio-head">
        <h1>Strategy studio</h1>
        <p>Signal, filter, size, allocate, then validate. Each step is a page of its own; this view strings them together and shows where you are. {done} of {STEPS.length} steps have a finished run.</p>
      </header>
      <ol className="studio-steps">
        {STEPS.filter((s) => have.has(s.id)).map((s, i) => {
          const run = latest(s.id);
          const meta = metaFor(s.id);
          const Icon = meta.icon;
          return (
            <li key={s.id} data-done={run?.status === "completed" || undefined}>
              <span className="studio-num num">{i + 1}</span>
              <div className="studio-card">
                <div className="studio-card-h">
                  <Icon size={15} aria-hidden />
                  <b>{s.step}</b>
                  <span className="studio-page">{meta.name}</span>
                  <Status run={run} />
                </div>
                <p>{s.does}</p>
                {run?.headline ? <p className="studio-headline" style={{ borderColor: TONE[run.tone ?? ""] ?? "var(--line-2)" }}>{run.headline}</p> : null}
                <div className="studio-foot">
                  {s.next ? <span>{s.next}</span> : <span />}
                  <Link href={featureHref(s.id)} className="btn">{run ? "Open" : "Start"}<ArrowRight size={13} /></Link>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
