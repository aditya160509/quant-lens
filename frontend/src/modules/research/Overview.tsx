"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
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

export function Overview({ features, loading, runs }: { features: FeatureSpec[]; loading: boolean; runs: RunRecord[] }) {
  const tested = features.filter((f) => latestRun(runs, f.id));
  const pass = tested.filter((f) => latestRun(runs, f.id)?.tone === "up").length;
  return (
    <div className="island" style={{ overflowY: "auto" }}>
      <div style={{ padding: "26px 26px 30px", maxWidth: 1320, width: "100%" }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em" }}>Research</h1>
        <p style={{ margin: "6px 0 18px", color: "var(--text-3)", maxWidth: 680, fontSize: 13.5, lineHeight: 1.55 }}>
          Every way to test a trading signal, from asset-pricing regressions to causal designs. Run a test, read the verdict, then dig into the evidence.
        </p>
        <div className="kpis" style={{ maxWidth: 640, marginBottom: 22 }}>
          <div className="kpi"><div className="l">Tests available</div><div className="v">{features.length || "–"}</div></div>
          <div className="kpi"><div className="l">Tested on this device</div><div className="v">{tested.length}</div></div>
          <div className="kpi"><div className="l">Passing</div><div className="v" style={{ color: pass ? "var(--up)" : undefined }}>{pass}</div></div>
        </div>
        <div className="ov-grid">
          {loading
            ? Array.from({ length: 10 }, (_, i) => <div key={i} className="ov-card"><span className="skel" style={{ width: 32, height: 32 }} /><span className="skel" style={{ width: "60%", height: 12, marginTop: 14 }} /><span className="skel" style={{ width: "90%", height: 10, marginTop: 10 }} /></div>)
            : features.map((f, i) => {
              const m = metaFor(f.id, f.name);
              const Icon = m.icon;
              const last = latestRun(runs, f.id);
              return (
                <motion.div key={f.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.03, ease: [0.2, 0, 0, 1] }}>
                  <Link href={featureHref(f.id)} className="ov-card" style={{ height: "100%" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="ov-icon"><Icon size={16} strokeWidth={1.7} /></span>
                      <span style={{ fontWeight: 600, color: "var(--text)", fontSize: 14 }}>{m.name}</span>
                      <ArrowUpRight size={14} className="ov-arrow" />
                    </div>
                    <p className="ov-desc">{m.question} {f.description}</p>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: "auto" }}>
                      {last ? (
                        <>
                          <Dot tone={last.tone ?? null} />
                          <span className="ov-head">{last.headline?.split(/(?<=\.)\s/)[0] ?? "Completed"}</span>
                          <span className="num" style={{ marginLeft: "auto", color: "var(--text-3)", fontSize: 11, flex: "none" }}>{ago(last.startedAt)}</span>
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
      </div>
    </div>
  );
}
