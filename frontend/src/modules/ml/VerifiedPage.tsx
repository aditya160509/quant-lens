"use client";

import { Exhibit } from "@/kit/Exhibit";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Copy } from "lucide-react";
import { useState } from "react";
import { get } from "@/modules/research/api";
import type { FeatureResult, FeatureSpec } from "@/modules/research/types";
import { takeaway } from "./takeaways";
import { ValAutopsy, ValControls, ValCostCurve, ValCpcv, ValLeakage, ValMonteCarlo, ValOverfit, ValPlateau, ValReceipt, ValTransfer, ValVerdict, verdictOf } from "./validateViews";

type Stamped = { id: string; sha256: string; created_at: string; result: FeatureResult };

const SPEC: FeatureSpec = { id: "mlvalidate", name: "Validate my strategy", description: "", inputs: [], outputs: [] };
const TONE: Record<string, string> = { "HELD UP": "var(--up)", MIXED: "var(--warn)", FAILED: "var(--down)" };

const CARDS = [
  ["The verdict and every check behind it", ValVerdict, "autopsy"],
  ["Overfitting autopsy", ValAutopsy, "autopsy"],
  ["Against simple alternatives", ValControls, "controls"],
  ["Sharpe as costs rise", ValCostCurve, "autopsy"],
  ["Purged cross-validation", ValCpcv, "cpcv"],
  ["Block bootstrap", ValMonteCarlo, "monte_carlo"],
  ["Out-of-sample transfer", ValTransfer, "transfer"],
  ["Parameter sweep", ValPlateau, "plateau"],
  ["Trial count and history", ValOverfit, "deflated_sharpe"],
  ["Look-ahead audit", ValLeakage, "leakage"],
  ["Reproducibility receipt", ValReceipt, "receipt"],
] as const;

const WIDE = new Set(["The verdict and every check behind it", "Against simple alternatives", "Reproducibility receipt"]);

/** A frozen Validate result: read-only, stamped with the hash of its content, shareable by link. */
export function VerifiedPage({ id }: { features: FeatureSpec[]; id?: string }) {
  const q = useQuery({ queryKey: ["ml", "verified", id], queryFn: () => get<Stamped>(`/verified/${id}`), enabled: Boolean(id), staleTime: Infinity, retry: false });
  const [copied, setCopied] = useState(false);
  if (q.isLoading) return <div className="verified"><div className="skeleton" style={{ height: 160 }} /></div>;
  if (q.isError || !q.data) return <div className="verified"><p className="ml-note">This verified result does not exist or has been removed.</p></div>;
  const { result, sha256, created_at } = q.data;
  const v = verdictOf(result);
  const tone = TONE[v?.label ?? ""] ?? "var(--text-2)";
  return (
    <div className="verified">
      <header className="verified-head" style={{ ["--tone" as string]: tone }}>
        <span className="verified-badge"><BadgeCheck size={14} />Verified result</span>
        <h1><span className="verified-stamp">{v?.label}</span>{v?.headline}</h1>
        <div className="verified-ribbon num" aria-label="Content hash">{sha256.match(/.{1,8}/g)?.join(" ")}</div>
        <div className="verified-meta">
          <span>Published {new Date(created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</span>
          <button type="button" className="val-hash num" onClick={() => { void navigator.clipboard?.writeText(sha256); setCopied(true); setTimeout(() => setCopied(false), 1200); }} title="Copy the SHA-256 of this result">
            sha256 {sha256.slice(0, 16)}…<Copy size={11} />{copied ? " copied" : ""}
          </button>
          <span>Read-only: the result is frozen server-side under this hash and cannot be edited.</span>
        </div>
      </header>
      <div className="verified-grid">
        {CARDS.map(([title, View, key], i) => (
          <Exhibit key={title} id={key} className="verified-card" wide={WIDE.has(title)} level={2} index={i + 1} name={title}
            finding={(View === ValCostCurve || View === ValVerdict ? null : takeaway("mlvalidate", key, undefined, result)) ?? title}>
            <View rows={[]} result={result} feature={SPEC} keys={[key]} scope={`verified:${q.data.id}`} />
          </Exhibit>
        ))}
      </div>
    </div>
  );
}
