"use client";

import { ArrowRight, Check, Circle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useStudies } from "@/modules/research/store";
import { defaultsFor, toPayload, validate } from "@/modules/research/StudyForm";
import { verdictFor } from "@/modules/research/layouts";
import { get, post, metricsOf, useRuns } from "@/modules/research/api";
import { featureHref, metaFor } from "@/modules/research/catalog";
import { lab } from "@/modules/research/lab";
import type { FeatureSpec, RunRecord, Job } from "@/modules/research/types";

/** The thin strategy studio: the four pages as one pipeline, each step showing its latest run and where it hands off. */
const STEPS = [
  { id: "ml02", step: "Signal" },
  { id: "ml04", step: "Filter" },
  { id: "ml03", step: "Size" },
  { id: "ml05", step: "Allocate" },
  { id: "mlvalidate", step: "Validate" },
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
  const [pipeline, setPipeline] = useState<{ index: number; alpha?: string; allocation?: string; error?: string; stopped?: boolean } | null>(null);
  const [working, setWorking] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const live = working && !pipeline?.stopped;
  const start = async () => {
    if (controller.current) return;
    const abort = new AbortController();
    controller.current = abort;
    setWorking(true);
    setPipeline({ index: 0 });
    let alpha: string | undefined, allocation: string | undefined;
    try {
      for (let index = 0; index < STEPS.length; index++) {
        if (abort.signal.aborted) break;
        const feature = features.find((f) => f.id === STEPS[index].id);
        if (!feature) throw new Error(`The ${STEPS[index].step} study is unavailable.`);
        setPipeline({ index, alpha, allocation });
        const form = { ...defaultsFor(feature), ...useStudies.getState().forms[feature.id] };
        if (feature.id === "ml04") { form.artifact_id = alpha; form.upload_id = ""; }
        if (feature.id === "ml05") form.alpha_artifact_id = alpha;
        if (feature.id === "mlvalidate") { form.artifact_id = allocation; form.upload_id = ""; }
        const errors = validate(feature, form);
        if (Object.keys(errors).length) throw new Error(`${metaFor(feature.id).name}: ${Object.entries(errors).map(([k, v]) => `${k}: ${v}`).join("; ")}. Open that page to correct its Study settings.`);
        const payload = toPayload(feature, form);
        const request = lab().submit(feature.id, payload);
        const submitted = await post<{ job_id: string; status: Job["status"] }>(request.path, request.body);
        useRuns.getState().add({ jobId: submitted.job_id, featureId: feature.id, featureName: feature.name, startedAt: Date.now(), status: submitted.status, payload, log: [{ t: Date.now(), text: "Started from Strategy studio" }] });
        let result: Job["result"];
        while (!abort.signal.aborted) {
          const data = await get<Job>(`/jobs/${encodeURIComponent(submitted.job_id)}`);
          useRuns.getState().update(submitted.job_id, { status: data.status });
          if (data.status === "completed") { result = data.result; break; }
          if (data.status === "failed" || data.status === "cancelled") throw new Error(data.error ?? `Run ${data.status}. Later stages were not started.`);
          await new Promise<void>((resolve) => {
            const finish = () => { clearTimeout(timer); abort.signal.removeEventListener("abort", finish); resolve(); };
            const timer = setTimeout(finish, 2000);
            abort.signal.addEventListener("abort", finish, { once: true });
          });
        }
        if (abort.signal.aborted) break;
        if (!result) throw new Error("The completed run has no result. Later stages were not started.");
        const verdict = verdictFor(feature, result);
        useRuns.getState().update(submitted.job_id, { headline: verdict.headline ?? undefined, tone: verdict.tone ?? undefined, metrics: metricsOf(result) });
        const artifact = typeof result.meta.artifact_id === "string" ? result.meta.artifact_id : undefined;
        if ((feature.id === "ml02" || feature.id === "ml05") && !artifact) throw new Error("This run returned no hand-off artifact. Later stages were not started; open the run to inspect its result.");
        if (feature.id === "ml02") alpha = artifact;
        if (feature.id === "ml05") allocation = artifact;
        setPipeline({ index: index + 1, alpha, allocation });
      }
    } catch (error) {
      if (!abort.signal.aborted) setPipeline((p) => ({ index: p?.index ?? 0, alpha, allocation, error: error instanceof Error ? error.message : "Pipeline failed. Open the active study to inspect its result." }));
    } finally {
      controller.current = null;
      setWorking(false);
    }
  };
  const have = new Set(features.map((f) => f.id));
  const latest = (id: string) => runs.find((r) => r.featureId === id);
  const done = STEPS.filter((s) => latest(s.id)?.status === "completed").length;
  return (
    <div className="studio">
      <header className="studio-head">
        <h1>Strategy studio</h1>
        <p>{done} / {STEPS.length} completed · Saved Study settings</p>
        <div className="studio-actions">
          <button className="btn primary" disabled={working || !STEPS.every((s) => have.has(s.id))} onClick={() => void start()}>Run the whole pipeline</button>
          {live ? <button className="btn" onClick={() => { controller.current?.abort(); setPipeline((p) => p ? { ...p, stopped: true } : p); }}>Stop later stages</button> : null}
        </div>
        {pipeline ? <p role={pipeline.error ? "alert" : "status"}>{pipeline.error ?? (pipeline.stopped ? "Pipeline stopped. Any submitted run continues in Runs; no later stages will start." : pipeline.index === STEPS.length ? "All five studies completed. Review the verdicts before acting." : `Stage ${pipeline.index + 1} of ${STEPS.length}: ${STEPS[pipeline.index].step}`)}</p> : null}

      </header>
      <ol className="studio-steps">
        {STEPS.filter((s) => have.has(s.id)).map((s, i) => {
          const run = latest(s.id);
          const source = s.id === "ml04" || s.id === "ml05" ? { name: "Signal", id: pipeline?.alpha } : s.id === "mlvalidate" ? { name: "Allocation", id: pipeline?.allocation } : null;
          const meta = metaFor(s.id);
          const Icon = meta.icon;
          return (
            <li key={s.id} data-done={run?.status === "completed" || undefined}>
              <span className="studio-num num">{i + 1}</span>
              <div className="studio-card">
                <div className="studio-card-h">
                  <Icon size={15} aria-hidden />
                  <b>{s.step}</b>

                  <Status run={run} />
                </div>
                {source ? <div className="studio-input"><span>{source.name} → {s.step}</span>{source.id ? <code>{source.id}</code> : <span>Awaiting artifact</span>}</div> : <span className="studio-input">{s.id === "ml03" ? "Independent study" : "Universe + features"}</span>}
                {run?.headline ? <p className="studio-headline" style={{ borderColor: TONE[run.tone ?? ""] ?? "var(--line-2)" }}>{run.headline}</p> : null}
                <div className="studio-foot">

                  <Link href={`${featureHref(s.id)}${run ? `?run=${encodeURIComponent(run.jobId)}` : ""}`} className="btn">{run ? "Open" : "Start"}<ArrowRight size={13} /></Link>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
