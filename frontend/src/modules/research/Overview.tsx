"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { DUR } from "@/workspace/prefs";
import { Chip, Dot } from "@/workspace/ui";
import { latestRun, useJob } from "./api";
import { cardId, usePins, type Pin } from "./cardPrefs";
import { layoutFor } from "./layouts";
import { OutputCard } from "./OutputCard";
import { Onboarding } from "./Onboarding";
import { featureHref, metaFor } from "./catalog";
import { lab, owns } from "./lab";
import type { FeatureSpec, RunRecord } from "./types";

const ago = (t: number) => {
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
};

/** The order a signal moves through: does it price, does it survive, is it causal, is it publishable. */
const STAGES: { id: string; label: string; intro: string; ids: string[] }[] = [
  { id: "test", label: "Test", intro: "Does the signal earn a premium? Model checks run with it.", ids: ["01"] },
  { id: "stress", label: "Stress", intro: "Does it survive other choices, fake signals and different market regimes?", ids: ["02", "03"] },
  { id: "explain", label: "Explain", intro: "Is the effect causal, and is it fading or already a known factor?", ids: ["07", "08"] },
];

const TONE_TEXT = { up: "Pass", down: "Fail", warn: "Mixed" } as const;
const fmtMetric = (v: number) => (Number.isInteger(v) ? v.toLocaleString() : Math.abs(v) < 0.1 ? v.toFixed(4) : v.toFixed(3));

export function Overview({ features, loading, runs }: { features: FeatureSpec[]; loading: boolean; runs: RunRecord[] }) {
  const last = features.map((f) => latestRun(runs, f.id)).filter((r): r is RunRecord => Boolean(r));
  const count = (t: RunRecord["tone"]) => last.filter((r) => r.tone === t).length;
  const byId = new Map(features.map((f) => [f.id, f]));
  const L = lab();
  if (L.overview?.home) return <L.overview.home features={features} runs={runs} />;
  const stages = (L.overview?.stages ?? STAGES).filter((s) => s.ids.some((id) => byId.has(id)));
  const W = L.overview?.words ?? { tests: "Tests", pass: "Pass", mixed: "Mixed", fail: "Fail" };
  const stats: [string, string | number, string?][] = [
    [W.tests, features.length || "–"],
    ["Run", `${last.length}/${features.length || 0}`],
    [W.pass, count("up"), "var(--up)"],
    [W.mixed, count("warn"), "var(--warn)"],
    [W.fail, count("down"), "var(--down)"],
    ["Last run", runs[0] ? ago(runs[0].startedAt) : "–"],
  ];

  return (
    <div className="island" style={{ overflowY: "auto" }}>
      <div style={{ padding: "26px 26px 34px", maxWidth: 1320, width: "100%" }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em" }}>{L.title}</h1>
        <p style={{ margin: "6px 0 20px", color: "var(--text-3)", maxWidth: 680, fontSize: 13.5, lineHeight: 1.55 }}>
          {L.overview?.intro ?? "Every way to test a trading signal, from asset-pricing regressions to causal designs. Work left to right: test it, stress it, explain it, publish it."}
        </p>
        <div className="ov-stats">
          {stats.map(([l, v, c]) => (
            <div key={l}><div className="l">{l}</div><div className="v" style={{ color: c && v ? c : undefined }}>{v}</div></div>
          ))}
        </div>

        {L.overview?.today && L.overview.actions?.some((a) => latestRun(runs, a.id)?.status === "completed") ? <L.overview.today features={features} runs={runs} /> : L.overview?.actions?.length ? (
          <div className="ov-actions">
            {L.overview.actions.filter((a) => byId.has(a.id)).map((a) => {
              const m = metaFor(a.id);
              const Icon = m.icon;
              const run = latestRun(runs, a.id);
              const tone = run?.tone === "up" ? "var(--up)" : run?.tone === "down" ? "var(--down)" : run?.tone === "warn" ? "var(--warn)" : "var(--accent)";
              return (
                <Link key={a.id} href={featureHref(a.id)} className="ov-action" style={{ ["--tone" as string]: tone }}>
                  <span className="ov-action-icon"><Icon size={18} strokeWidth={1.7} /></span>
                  <b>{a.title}</b>
                  {run?.headline ? <span className="ov-action-last">{run.headline}</span> : <span>{a.body}</span>}
                  <em>{run ? `Last run ${ago(run.startedAt)} · open` : a.cta} →</em>
                </Link>
              );
            })}
          </div>
        ) : null}
        {L.signal || L.id === "ml" ? <Onboarding ml={L.id === "ml"} /> : null}
        <Board features={features} />

        {stages.map((stage, si) => (
          <section key={stage.id} style={{ marginTop: 26 }}>
            <div className="ov-stage">
              <span className="n">{si + 1}</span>
              <h2>{stage.label}</h2>
              {stage.intro ? <p>{stage.intro}</p> : null}
            </div>
            <div className="ov-grid">
              {loading
                ? stage.ids.map((id) => <div key={id} className="ov-card"><span className="skel" style={{ width: 32, height: 32 }} /><span className="skel" style={{ width: "60%", height: 12, marginTop: 14 }} /></div>)
                : stage.ids.map((id) => byId.get(id)).filter((f): f is FeatureSpec => Boolean(f)).map((f, i) => {
                  const m = metaFor(f.id, f.name);
                  const Icon = m.icon;
                  const run = latestRun(runs, f.id);
                  const metrics = Object.entries(run?.metrics ?? {}).slice(0, 3);
                  const tone = run?.tone ?? null;
                  return (
                    <motion.div key={f.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.base, delay: Math.min(0.12, (si * 3 + i) * 0.015) }}>
                      <Link href={featureHref(f.id)} className={`ov-card${tone ? ` t-${tone}` : ""}`} style={{ height: "100%" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span className="ov-icon"><Icon size={16} strokeWidth={1.7} /></span>
                          <span style={{ fontWeight: 600, color: "var(--text)", fontSize: 14 }}>{m.name}</span>
                          {tone ? <Chip tone={tone}>{TONE_TEXT[tone]}</Chip> : null}
                          <ArrowUpRight size={14} className="ov-arrow" />
                        </div>
                        <p className="ov-desc">{m.question}</p>
                        {metrics.length ? (
                          <div className="ov-metrics">
                            {metrics.map(([k, v]) => <div key={k}><span>{k}</span><b className="num">{fmtMetric(v)}</b></div>)}
                          </div>
                        ) : null}
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: "auto", paddingTop: 12 }}>
                          {run ? (
                            <>
                              <Dot tone={tone} live={run.status === "running" || run.status === "queued"} />
                              <span className="ov-head">{run.headline?.split(/(?<=\.)\s/)[0] ?? (run.status === "completed" ? "Completed" : run.status)}</span>
                              <span className="num" style={{ marginLeft: "auto", color: "var(--text-3)", fontSize: 11, flex: "none" }}>{ago(run.startedAt)}</span>
                            </>
                          ) : (
                            <><Chip>Not run yet</Chip><span className="num" style={{ marginLeft: "auto", color: "var(--text-4)", fontSize: 11 }}>{f.outputs.length} outputs</span></>
                          )}
                        </div>
                      </Link>
                    </motion.div>
                  );
                })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

/** Pinned outputs from any feature, side by side, each drawn from the run it was pinned from. */
function Board({ features }: { features: FeatureSpec[] }) {
  const pins = usePins((s) => s.pins).filter((p) => owns(p.featureId));
  if (!pins.length || !features.length) return null;
  return (
    <section style={{ marginTop: 26 }}>
      <div className="ov-stage"><span className="n">★</span><h2>Board</h2><p>Outputs you pinned. Right-click any output and choose Pin to board.</p></div>
      <div className="out-grid">
        {pins.map((p) => <PinnedCard key={`${p.featureId}:${p.card}`} pin={p} features={features} />)}
      </div>
    </section>
  );
}

function PinnedCard({ pin, features }: { pin: Pin; features: FeatureSpec[] }) {
  const feature = features.find((f) => f.id === pin.featureId);
  const job = useJob(pin.jobId);
  const remove = usePins((s) => s.remove);
  const item = feature ? layoutFor(feature).sections.flatMap((s) => s.items).find((i) => cardId(i) === pin.card) : undefined;
  const result = job.data?.status === "completed" ? job.data.result : null;
  if (!feature || !item) return null;
  const span = Math.max(6, item.span);
  if (!result) {
    return (
      <div className="card" style={{ gridColumn: `span ${span}`, height: 160 }}>
        <div className="card-b" style={{ color: "var(--text-3)", fontSize: 12.5, display: "grid", gap: 8 }}>
          <b style={{ color: "var(--text)" }}>{metaFor(feature.id, feature.name).name}</b>
          {job.isLoading ? "Loading…" : "This run is no longer on the server. Re-run the feature and pin it again."}
          <button className="btn sm ghost" style={{ justifySelf: "start" }} onClick={() => remove(pin.card, pin.featureId)}>Remove</button>
        </div>
      </div>
    );
  }
  return (
    <div style={{ gridColumn: `span ${span}`, minWidth: 0 }}>
      <OutputCard item={{ ...item, title: `${metaFor(feature.id, feature.name).name} · ${item.title ?? feature.outputs.find((o) => o.key === item.keys[0])?.title ?? item.keys[0]}` }}
        feature={feature} result={result} maximized={false} onToggleMax={() => undefined} onHide={() => remove(pin.card, pin.featureId)} scope={`${feature.id}:${pin.jobId}`} />
    </div>
  );
}
