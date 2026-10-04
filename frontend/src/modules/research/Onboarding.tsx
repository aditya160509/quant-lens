"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { useActiveSignal, useRuns } from "./api";

const KEY = "research-onboarding-v1";
const STEPS = [
  { label: "Load momentum on the Signal page", href: "/research/signal" },
  { label: "Run the report card", href: "/research/report" },
  { label: "Open Robustness", href: "/research/robustness" },
];
type State = { done: number[]; dismissed: boolean };

function load(): State {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? ""); if (v && Array.isArray(v.done)) return v; } catch { /* unavailable */ }
  return { done: [], dismissed: false };
}

/** Dismissible 60-second first run; progress persists on this device. */
export function Onboarding() {
  const [st, setSt] = useState<State | null>(null);
  // Someone who has already run studies is not new: the quick start is for the first session only.
  const experienced = useRuns((r) => r.runs.filter((x) => x.status === "completed").length >= 3);
  const hasSignal = useActiveSignal((a) => Boolean(a.expr));
  useEffect(() => { const id = setTimeout(() => setSt(load()), 0); return () => clearTimeout(id); }, []);
  const save = (n: State) => { setSt(n); try { localStorage.setItem(KEY, JSON.stringify(n)); } catch { /* ignore */ } };
  if (!st || experienced || st.dismissed || st.done.length >= STEPS.length) return null;
  const isDone = (i: number) => st.done.includes(i) || (i === 0 && hasSignal);
  const toggle = (i: number) => save({ ...st, done: st.done.includes(i) ? st.done.filter((d) => d !== i) : [...st.done, i] });
  return (
    <div className="card" style={{ padding: 14, position: "relative", height: "auto", marginTop: 14 }} role="region" aria-label="Quick start">
      <button aria-label="Dismiss quick start" onClick={() => save({ ...st, dismissed: true })} style={{ position: "absolute", top: 10, right: 10 }}><X size={14} /></button>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>Your first report in 60 seconds</div>
      <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8 }}>{st.done.length} of {STEPS.length} done</div>
      <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
        {STEPS.map((s, i) => (
          <li key={s.label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <button aria-label={`Mark step ${i + 1} ${st.done.includes(i) ? "not done" : "done"}`} onClick={() => toggle(i)}
              style={{ width: 18, height: 18, borderRadius: 9, border: "1px solid var(--accent-line)", display: "grid", placeItems: "center", background: isDone(i) ? "var(--accent)" : "transparent" }}>
              {isDone(i) ? <Check size={11} /> : null}
            </button>
            <Link href={s.href} onClick={() => !st.done.includes(i) && toggle(i)} style={{ color: "var(--text)", textDecoration: isDone(i) ? "line-through" : "none" }}>{i + 1}. {s.label}</Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
