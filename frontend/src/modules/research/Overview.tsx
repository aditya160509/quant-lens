"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { DUR } from "@/workspace/prefs";
import { Chip, Dot } from "@/workspace/ui";
import { latestRun } from "./api";
import { featureHref, metaFor } from "./catalog";
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
  { id: "test", label: "Test", intro: "Does the signal earn a premium, and is the model well specified?", ids: ["01", "05"] },
  { id: "stress", label: "Stress", intro: "Does it survive other choices, fake signals and different market regimes?", ids: ["02", "03", "04"] },
  { id: "explain", label: "Explain", intro: "Is the effect causal, and is it fading as it gets traded?", ids: ["07", "09", "08"] },
  { id: "publish", label: "Publish", intro: "Does it clear the factor-zoo hurdle, and what goes in the paper?", ids: ["11", "06"] },
];

const TONE_TEXT = { up: "Pass", down: "Fail", warn: "Mixed" } as const;
const fmtMetric = (v: number) => (Number.isInteger(v) ? v.toLocaleString() : Math.abs(v) < 0.1 ? v.toFixed(4) : v.toFixed(3));

export function Overview({ features, loading, runs }: { features: FeatureSpec[]; loading: boolean; runs: RunRecord[] }) {
  const last = features.map((f) => latestRun(runs, f.id)).filter((r): r is RunRecord => Boolean(r));
  const count = (t: RunRecord["tone"]) => last.filter((r) => r.tone === t).length;
  const byId = new Map(features.map((f) => [f.id, f]));
  const placed = new Set(STAGES.flatMap((s) => s.ids));
  const stages = [...STAGES, { id: "other", label: "Other", intro: "", ids: features.map((f) => f.id).filter((id) => !placed.has(id)) }].filter((s) => s.ids.some((id) => byId.has(id)));
  const stats: [string, string | number, string?][] = [
    ["Tests", features.length || "–"],
    ["Tested", `${last.length}/${features.length || 0}`],
    ["Pass", count("up"), "var(--up)"],
    ["Mixed", count("warn"), "var(--warn)"],
    ["Fail", count("down"), "var(--down)"],
    ["Last run", runs[0] ? ago(runs[0].startedAt) : "–"],
  ];

  return (
    <div className="island" style={{ overflowY: "auto" }}>
      <div style={{ padding: "26px 26px 34px", maxWidth: 1320, width: "100%" }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em" }}>Research</h1>
        <p style={{ margin: "6px 0 20px", color: "var(--text-3)", maxWidth: 680, fontSize: 13.5, lineHeight: 1.55 }}>
          Every way to test a trading signal, from asset-pricing regressions to causal designs. Work left to right: test it, stress it, explain it, publish it.
        </p>
        <div className="ov-stats">
          {stats.map(([l, v, c]) => (
            <div key={l}><div className="l">{l}</div><div className="v" style={{ color: c && v ? c : undefined }}>{v}</div></div>
          ))}
        </div>

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
