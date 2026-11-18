"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { History, Keyboard, Play, RotateCcw } from "lucide-react";
import { Dot, Segmented } from "@/workspace/ui";
import { featureHref, metaFor } from "./catalog";
import { runLabel } from "./lab";
import { studyPart } from "./api";
import { out } from "./format";
import { layoutFor } from "./layouts";
import { DataWindow } from "./DataWindow";
import { cardId, useCardPrefs, useFeaturePrefs } from "./cardPrefs";
import type { FeatureRun } from "./ResearchApp";
import { useSelection } from "./selection";
import { defaultsFor, StudyForm, toPayload } from "./StudyForm";
import type { FeatureSpec, RunRecord } from "./types";

type View = "study" | "inspect";

export function Inspector({ feature, run, initial = null }: { feature: FeatureSpec; run: FeatureRun; initial?: View | null }) {
  // The user's explicit choice wins; otherwise show results once there are any.
  const [picked, setView] = useState<View | null>(initial);
  const selection = useSelection((s) => s.selection);
  const select = useSelection((s) => s.select);
  const running = ["submitting", "queued", "running"].includes(run.status);
  const view: View = picked ?? (run.result ? "inspect" : "study");
  const changedFromRun = !running && run.stale;

  useEffect(() => () => select(null), [feature.id, select]);
  useEffect(() => {
    const clear = (e: KeyboardEvent) => { if (e.key === "Escape") select(null); };
    window.addEventListener("keydown", clear);
    return () => window.removeEventListener("keydown", clear);
  }, [select]);

  return (
    <aside className="island" aria-label="Inspector">
      <div style={{ padding: 10 }}>
        <Segmented<View> label="Inspector view" value={view} onChange={setView} options={[{ value: "study", label: "Study" }, { value: "inspect", label: "Inspect" }]} />
      </div>

      {view === "study" ? (
        <>
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", borderTop: "1px solid var(--line)" }}>
            {changedFromRun ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, margin: 10, padding: "8px 10px", borderRadius: 9, background: "var(--accent-soft)", fontSize: 12, color: "var(--text-2)" }}>
                <History size={13} style={{ color: "var(--accent)", flex: "none" }} />
                <span style={{ flex: 1 }}>
                  {(() => {
                    const a = studyPart(toPayload(feature, run.form)) ?? {}, b = studyPart(toPayload(feature, { ...defaultsFor(feature), ...run.record?.payload })) ?? {};
                    const keys = Object.keys({ ...a, ...b }).filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
                    const name = (k: string) => feature.inputs.find((f) => f.key === k)?.label ?? k;
                    return keys.length ? <>{keys.length} setting{keys.length > 1 ? "s" : ""} changed since the run on screen: {keys.slice(0, 4).map(name).join(", ")}{keys.length > 4 ? "…" : ""}</> : "Settings differ from the run on screen.";
                  })()}
                </span>
                <button className="btn sm ghost" onClick={run.restore}>Restore</button>
              </div>
            ) : null}
            <StudyForm feature={feature} form={run.form} setForm={run.setForm} errors={run.errors} />
          </div>
          <footer style={{ display: "flex", gap: 6, padding: 10, borderTop: "1px solid var(--line)" }}>
            <button className="btn icon" onClick={run.reset} aria-label="Reset every setting to its default" title="Reset every setting"><RotateCcw size={13} /></button>
            <button className="btn primary" style={{ flex: 1, justifyContent: "center", height: 34 }} onClick={run.run} disabled={running}>
              <Play size={11} fill="currentColor" />{running ? "Running" : runLabel(feature.id)}
              <span className="kbd" style={{ background: "transparent", color: "inherit", boxShadow: "none", opacity: 0.55 }}>⌘↵</span>
            </button>
          </footer>
        </>
      ) : (
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto", borderTop: "1px solid var(--line)" }}>
          {selection ? (
            <section style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)" }}>
              <h4 className="insp-h">{selection.title}</h4>
              <dl style={{ margin: 0, display: "grid" }}>
                {selection.rows.map(([k, v]) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "6px 0", fontSize: 12.5, borderBottom: "1px solid var(--grid)" }}>
                    <dt style={{ color: "var(--text-3)" }}>{k}</dt>
                    <dd style={{ margin: 0, color: "var(--text)", textAlign: "right" }}>{v}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}
          <DataWindow />
          <Outline feature={feature} run={run} />
        </div>
      )}
    </aside>
  );
}

function Outline({ feature, run }: { feature: FeatureSpec; run: FeatureRun }) {
  const layout = layoutFor(feature);
  const result = run.result;
  const prefs = useFeaturePrefs(feature.id);
  const setPref = useCardPrefs((st) => st.set);
  const resetPrefs = useCardPrefs((st) => st.reset);
  return (
    <details open style={{ padding: "14px 8px" }}>
      <summary className="insp-h" style={{ padding: "0 8px", display: "flex", alignItems: "center", cursor: "pointer" }}>Outputs
        {Object.keys(prefs).length ? <button className="btn sm ghost" style={{ marginLeft: "auto", height: 22 }} onClick={(e) => { e.preventDefault(); resetPrefs(feature.id); }}>Reset layout</button> : null}
      </summary>
      {layout.sections.map((s) => (
        <div key={s.id} style={{ marginBottom: 8 }}>
          <div style={{ padding: "4px 8px", fontSize: 11.5, color: "var(--text-4)", fontWeight: 500 }}>{s.label}</div>
          {s.items.map((i) => {
            const spec = feature.outputs.find((o) => o.key === i.keys[0]);
            const has = result ? i.keys.some((k) => out(result, k).length > 0) : false;
            return (
              <div key={i.keys.join("+") + (i.view ?? "")} className="outline-row">
                <input type="checkbox" aria-label={`Show ${i.title ?? spec?.title ?? i.keys[0]}`} checked={!prefs[cardId(i)]?.hidden} disabled={!has}
                  onChange={(e) => setPref(feature.id, cardId(i), { hidden: !e.target.checked })} />
                <button className="outline-item" disabled={!has || prefs[cardId(i)]?.hidden}
                  onClick={() => window.dispatchEvent(new CustomEvent("research:jump", { detail: i.keys[0] }))}>
                  {i.title ?? spec?.title ?? i.keys[0]}
                </button>
              </div>
            );
          })}
        </div>
      ))}
    </details>
  );
}

const KEYS: [string, string][] = [["⌘K", "Search everything"], ["⌘↵", "Run the study"], ["⌘B", "Feature list"], ["⌘I", "Inspector"], ["⌘J", "Runs and log"], ["[ ]", "Previous / next section"], ["Esc", "Close an expanded card"]];

export function OverviewInspector({ runs }: { runs: RunRecord[] }) {
  return (
    <aside className="island" aria-label="Recent activity" style={{ overflowY: "auto" }}>
      <section style={{ padding: "16px 16px 6px" }}>
        <h4 className="insp-h">Recent runs</h4>
        {runs.length ? runs.slice(0, 8).map((r) => {
          const m = metaFor(r.featureId, r.featureName);
          const Icon = m.icon;
          return (
            <Link key={r.jobId} href={`${featureHref(r.featureId)}?run=${r.jobId}`} className="nav-item" style={{ margin: "1px -6px", height: "auto", padding: "8px 8px", alignItems: "flex-start" }}>
              <Icon size={14} strokeWidth={1.7} style={{ marginTop: 2 }} />
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{ display: "block", fontSize: 12.5, color: "var(--text)" }}>{m.name}</span>
                <span style={{ display: "block", fontSize: 11.5, color: "var(--text-3)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.headline ?? r.status}</span>
              </span>
              <Dot tone={r.tone ?? null} live={r.status === "running" || r.status === "queued"} />
            </Link>
          );
        }) : <p style={{ color: "var(--text-3)", fontSize: 12.5 }}>No runs yet. Pick a feature to start.</p>}
      </section>
      <section style={{ padding: "16px", marginTop: 8, borderTop: "1px solid var(--line)" }}>
        <h4 className="insp-h" style={{ display: "flex", alignItems: "center", gap: 6 }}><Keyboard size={13} />Shortcuts</h4>
        {KEYS.map(([k, d]) => (
          <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", fontSize: 12.5, color: "var(--text-2)" }}>{d}<span className="kbd">{k}</span></div>
        ))}
      </section>
    </aside>
  );
}
