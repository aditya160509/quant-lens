"use client";

import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/lib/apiBase";
import { layoutFor, verdictFor } from "./layouts";
import { metaFor } from "./catalog";
import { OutputCard } from "./OutputCard";
import { out } from "./format";
import type { FeatureResult, FeatureSpec } from "./types";

/** A shared run, read-only: the verdict and every output, no study panel. */
export function SharedView({ token, features }: { token: string; features: FeatureSpec[] }) {
  const q = useQuery({
    queryKey: ["research", "share", token],
    queryFn: async () => {
      const r = await fetch(`${API_BASE_URL}/labs/research/v2/share/${token}`);
      if (!r.ok) throw new Error(r.status === 404 ? "This link is not valid or was removed." : `Could not load (${r.status})`);
      return r.json() as Promise<{ feature_id: string; result: FeatureResult; created_at: string }>;
    },
    retry: false,
  });
  const feature = q.data ? features.find((f) => f.id === q.data.feature_id) : undefined;
  if (q.isError) return <div className="island" style={{ padding: 24, color: "var(--text-3)" }}>{(q.error as Error).message}</div>;
  if (!q.data || !feature) return <div className="island" style={{ padding: 24, color: "var(--text-3)" }}>Loading shared run…</div>;
  const result = q.data.result;
  const v = verdictFor(feature, result);
  const items = layoutFor(feature).sections.flatMap((s) => s.items).filter((i) => i.keys.some((k) => out(result, k).length));
  return (
    <div className="island" style={{ overflowY: "auto" }}>
      <div style={{ padding: "22px 22px 30px" }}>
        <div style={{ fontSize: 11.5, color: "var(--text-4)" }}>Shared run · read-only · {new Date(q.data.created_at).toLocaleString()}</div>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: "4px 0 6px" }}>{metaFor(feature.id, feature.name).name}</h1>
        {v.headline ? <p style={{ fontSize: 14, color: "var(--text-2)", marginBottom: 14 }}>{v.headline}</p> : null}
        <div className="out-grid">
          {items.map((i) => (
            <div key={i.keys.join("+") + (i.view ?? "")} style={{ gridColumn: `span ${i.span}`, minWidth: 0 }}>
              <OutputCard item={i} feature={feature} result={result} maximized={false} onToggleMax={() => undefined} scope={`${feature.id}:shared`} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
