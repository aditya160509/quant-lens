"use client";

import Link from "next/link";
import { useEffect } from "react";
import { RunContext } from "@/modules/research/FeatureView";
import { isNum, pct } from "@/modules/research/format";
import type { FeatureRun } from "@/modules/research/ResearchApp";
import type { FeatureSpec, InputSpec, Row } from "@/modules/research/types";
import { useHome, type Freshness, type Ledger } from "./api";
import { metaOf, type LimitRow } from "./types";
import "./studio.css";

const show = (row: LimitRow, v: number | null) => (v === null ? "—" : row.format === "pct" ? pct(v, 0) : row.format === "int" ? String(Math.round(v)) : v.toFixed(1));

/** "Drawdown 22% of 25% limit: 12% room": the condition nearest to failing, or the one that failed by most. */
export function closestCall(row: LimitRow | null): string | null {
  if (!row || row.value === null) return null;
  return `${row.limit} ${show(row, row.value)} of ${show(row, row.bound)} limit${isNum(row.room) ? `: ${row.room >= 0 ? `${pct(row.room, 0)} room` : `over by ${pct(-row.room, 0)}`}` : ""}`;
}

export function FreshnessPill({ f }: { f: Freshness }) {
  return <span className={`chip ${f.tone === "red" ? "down" : f.tone === "amber" ? "warn" : ""}`} data-testid="freshness">{f.label}</span>;
}

export function TrialChip({ ledger, strategyId }: { ledger: Ledger; strategyId?: string | null }) {
  const by = Object.entries(ledger.by_actor).map(([k, v]) => `${k.replace("_", " ")} ${v}`).join(", ");
  const text = `${ledger.raw.toLocaleString()} raw / ${ledger.effective.toLocaleString(undefined, { maximumFractionDigits: 1 })} effective trials`;
  return strategyId ? <Link className="chip" href={`/studio/library/agents?strategy=${strategyId}`} title={by || undefined} data-testid="trials">{text}</Link> : <span className="chip" title="Save the strategy to keep its trial count" data-testid="trials">{text}</span>;
}

/** Above every result, before the hero: My limits with the closest call, the cost ladder, and the pills every run carries. */
export function StudioContext({ feature, run }: { feature: FeatureSpec; run: FeatureRun }) {
  const r = run.result;
  const m = r ? metaOf(r) : null;
  const limits = (r?.tables.my_limits ?? []) as LimitRow[];
  const ladder = (r?.charts.cost_ladder ?? []) as { multiple: number; cagr: number | null }[];
  const printed = (r?.tables.limits ?? []) as Row[];
  return (
    <>
      <RunContext feature={feature} run={run} />
      {feature.id === "st04" ? <MemberChips run={run} /> : null}
      {m && r ? (
        <div className="st-strip" data-testid="studio-strip">
          {m.my_limits?.of ? (
            <details className="st-pop">
              <summary className={`chip ${m.my_limits.passed === m.my_limits.of ? "up" : "down"}`} data-testid="my-limits">Passes {m.my_limits.passed} of {m.my_limits.of}{closestCall(m.my_limits.closest) ? ` · ${closestCall(m.my_limits.closest)}` : ""}</summary>
              <div className="st-pop-b">
                {limits.map((x) => <div key={x.limit} className="st-row"><span>{x.limit}</span><b className="num">{show(x, x.value)}</b><span className="num">limit {show(x, x.bound)}</span><i className={x.pass === null ? "" : x.pass ? "up" : "down"}>{x.pass === null ? "—" : x.pass ? "pass" : "fail"}</i></div>)}
              </div>
            </details>
          ) : null}
          {ladder.length ? <span className="st-ladder num" data-testid="cost-ladder">Net CAGR {ladder.map((x) => `${pct(x.cagr)} at ${x.multiple}×`).join(", ")} costs</span> : null}
          <span style={{ flex: 1 }} />
          {m.costs_off ? <span className="chip warn" data-testid="costs-off">costs off</span> : null}
          {m.few_trades ? <span className="chip warn" title="Fewer than 30 trades: every statistic here is weak">few trades</span> : null}
          {printed.length ? <details className="st-pop right">
            <summary className="chip" data-testid="limits-pill">{printed.length} limits</summary>
            <div className="st-pop-b wide">{printed.map((x) => <div key={String(x.limit)} className="st-limit"><b>{String(x.limit)}</b><span>{String(x.detail)}</span></div>)}</div>
          </details> : null}
          {m.freshness ? <FreshnessPill f={m.freshness} /> : null}
          {m.ledger && feature.id !== "st04" ? <TrialChip ledger={m.ledger} strategyId={m.strategy?.id} /> : null}
          <Link className="chip" href="/studio/validate" data-testid="verdict-chip">{m.verdict_chip ?? "not validated"}</Link>
        </div>
      ) : null}
    </>
  );
}

/** The strategy this run uses: every saved strategy, latest version. */
export function StrategyPicker({ value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const home = useHome();
  const list = home.data?.strategies ?? [];
  // An empty picker takes the last strategy used on any Studio page, else the most recently edited one.
  useEffect(() => {
    if (typeof value === "string" && value) return;
    let last: string | null = null;
    try { last = localStorage.getItem("studio:strategy"); } catch { /* storage blocked */ }
    const pick = list.find((s) => s.id === last)?.id ?? list[0]?.id;
    if (pick) onChange(pick);
  }, [value, list, onChange]);
  return (
    <select className="input" aria-label="Strategy" value={typeof value === "string" ? value : ""} onChange={(e) => { try { localStorage.setItem("studio:strategy", e.target.value); } catch { /* storage blocked */ } onChange(e.target.value); }}>
      <option value="">{home.isLoading ? "Loading…" : list.length ? "Pick a strategy" : "No saved strategy yet"}</option>
      {list.map((s) => <option key={s.id} value={s.id}>{s.name} · v{s.version}</option>)}
    </select>
  );
}

/** Several strategies for Portfolio: ticked boxes, stored as space-separated ids (up to 8). */
export function StrategiesPicker({ value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const home = useHome();
  const list = home.data?.strategies ?? [];
  const picked = new Set(typeof value === "string" ? value.split(/[\s,]+/).filter(Boolean) : []);
  const toggle = (id: string) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else if (next.size < 8) next.add(id);
    onChange([...next].join(" "));
  };
  return (
    <div style={{ display: "grid", gap: 4 }}>
      {list.map((s) => (
        <label key={s.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12.5 }}>
          <input type="checkbox" checked={picked.has(s.id)} onChange={() => toggle(s.id)} />{s.name} · v{s.version}
        </label>
      ))}
      {!list.length ? <span className="bd-meta">{home.isLoading ? "Loading…" : "No saved strategy yet"}</span> : null}
    </div>
  );
}

/** Portfolio's members, picked in the strip (the inspector starts closed). */
function MemberChips({ run }: { run: FeatureRun }) {
  const home = useHome();
  const raw = run.form.strategy_ids;
  const picked = new Set(typeof raw === "string" ? raw.split(/[\s,]+/).filter(Boolean) : []);
  const toggle = (id: string) => run.setForm((cur) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else if (next.size < 8) next.add(id);
    return { ...cur, strategy_ids: [...next].join(" ") };
  });
  return (
    <div className="st-strip">
      {(home.data?.strategies ?? []).map((s) => (
        <button key={s.id} type="button" className={`chip${picked.has(s.id) ? " up" : ""}`} aria-pressed={picked.has(s.id)} onClick={() => toggle(s.id)}>{picked.has(s.id) ? "✓ " : ""}{s.name} v{s.version}</button>
      ))}
    </div>
  );
}
