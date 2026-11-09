"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "@/modules/research/api";
import type { InputSpec } from "@/modules/research/types";

type Template = { key: string; formula: string; weak_evidence: boolean };

/** Ready-made screens, each named by the formula it applies. */
export function TemplatePicker({ value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const templates = useQuery({ queryKey: ["screener", "templates"], queryFn: () => get<{ templates: Template[] }>("/templates"), staleTime: Infinity, retry: false });
  return (
    <div role="listbox" aria-label="Screen templates" style={{ maxHeight: 260, overflowY: "auto", display: "grid" }}>
      {(templates.data?.templates ?? []).map((t) => (
        <button key={t.key} type="button" role="option" aria-selected={value === t.key} className="btn sm ghost" style={{ justifyContent: "flex-start", textAlign: "left", height: "auto", padding: "5px 8px", whiteSpace: "normal" }} onClick={() => onChange(value === t.key ? "" : t.key)}>
          <span className="num" style={{ fontSize: 11.5 }}>{t.formula}</span>
          {t.weak_evidence ? <span className="chip warn" style={{ marginLeft: 6 }}>Weak evidence</span> : null}
        </button>
      ))}
    </div>
  );
}
