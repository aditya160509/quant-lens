"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ChevronDown, FileText, Loader2, Play, Square } from "lucide-react";
import { DUR } from "@/workspace/prefs";
import { PopMenu, Tabs, type MenuAt } from "@/workspace/ui";
import { metaFor } from "./catalog";
import { isNum, label, num, out } from "./format";
import { layoutFor, verdictFor, type Item, type Section } from "./layouts";
import { OutputCard } from "./OutputCard";
import type { FeatureRun } from "./ResearchApp";
import { Control } from "./StudyForm";
import type { FeatureResult, FeatureSpec, InputSpec } from "./types";

const RUNNING = new Set(["submitting", "queued", "running", "loading"]);

export function FeatureView({ feature, run }: { feature: FeatureSpec; run: FeatureRun }) {
  const layout = useMemo(() => layoutFor(feature), [feature]);
  const meta = metaFor(feature.id, feature.name);
  const Icon = meta.icon;
  const [tab, setTab] = useState(layout.sections[0]?.id ?? "");
  const [maxKey, setMaxKey] = useState<string | null>(null);
  const [stuck, setStuck] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [printing, setPrinting] = useState(false);
  // Report: render every section stacked, print once painted, then restore the tabbed view.
  useEffect(() => {
    if (!printing) return;
    const done = () => setPrinting(false);
    window.addEventListener("afterprint", done);
    const id = setTimeout(() => window.print(), 400);
    return () => { clearTimeout(id); window.removeEventListener("afterprint", done); };
  }, [printing]);
  const scroller = useRef<HTMLDivElement>(null);
  const hero = useRef<HTMLDivElement>(null);
  const running = RUNNING.has(run.status);
  const result = run.result;
  const visible = (s: Section) => (result ? s.items.filter((i) => i.keys.some((k) => out(result, k).length > 0)) : s.items);
  const shown = (s: Section) => visible(s).filter((i) => !hidden.has(i.keys[0]));
  const sections = result ? layout.sections.filter((s) => visible(s).length) : layout.sections;
  const active = sections.find((s) => s.id === tab) ?? sections[0];

  useEffect(() => {
    const el = hero.current;
    const root = scroller.current;
    if (!el || !root) return;
    const io = new IntersectionObserver(([e]) => setStuck(!e.isIntersecting), { root, threshold: 0, rootMargin: "-50px 0px 0px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMaxKey(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onJump = (e: Event) => {
      const key = (e as CustomEvent<string>).detail;
      const owner = layout.sections.find((s) => s.items.some((i) => i.keys.includes(key)));
      if (owner) setTab(owner.id);
      setMaxKey(null);
      setTimeout(() => {
        const el = document.getElementById(`out-${key}`);
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
        el?.classList.add("flash");
        setTimeout(() => el?.classList.remove("flash"), 1200);
      }, 60);
    };
    window.addEventListener("research:jump", onJump);
    return () => window.removeEventListener("research:jump", onJump);
  }, [layout]);

  const scope = `${feature.id}:${run.jobId ?? "draft"}`;
  const maxItem = maxKey && active ? active.items.find((i) => i.keys[0] === maxKey) : null;

  const runButton = (
    <div style={{ display: "flex", gap: 6, flex: "none" }}>
      {running && run.status !== "submitting" ? <button className="btn" onClick={run.cancel}><Square size={11} />Cancel</button> : null}
      <button className="btn primary" onClick={run.run} disabled={running} title="Run study (⌘↵)">
        {running ? <Loader2 size={13} className="spin" /> : <Play size={11} fill="currentColor" />}
        {running ? "Running" : result ? "Run again" : "Run study"}
        <span className="kbd" style={{ background: "transparent", color: "inherit", boxShadow: "none", opacity: 0.55 }}>⌘↵</span>
      </button>
    </div>
  );

  return (
    <div ref={scroller} className="island results" style={{ overflowY: "auto", overflowX: "hidden" }}>
      <div ref={hero} style={{ padding: "22px 22px 6px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div className="ov-icon" style={{ width: 40, height: 40, borderRadius: 11 }}><Icon size={19} strokeWidth={1.6} /></div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.2 }}>{meta.name}</h1>
            <p style={{ marginTop: 4, color: "var(--text-2)", fontSize: 13.5 }}>{meta.question}</p>
            <p style={{ marginTop: 6, color: "var(--text-3)", fontSize: 12.5, maxWidth: 860, lineHeight: 1.55 }}>{feature.description}</p>
          </div>
          {runButton}
        </div>
        <RunContext feature={feature} run={run} />
        <AnimatePresence initial={false}>
          {result ? (
            <motion.div key={run.jobId ?? "r"} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.slow, ease: [0.2, 0, 0, 1] }}>
              <VerdictStrip feature={feature} result={result} />
            </motion.div>
          ) : null}
        </AnimatePresence>
        {running ? <Progress startedAt={run.startedAt} status={run.status} /> : null}
      </div>

      <div className={`sticky-bar${stuck ? " stuck" : ""}`}>
        <span className="sticky-title"><Icon size={14} strokeWidth={1.7} style={{ color: "var(--accent)" }} />{meta.name}<span style={{ color: "var(--line-3)" }}>/</span></span>
        <Tabs value={active?.id ?? ""} onChange={(id) => { setTab(id); setMaxKey(null); scroller.current?.scrollTo({ top: Math.min(scroller.current.scrollTop, hero.current?.offsetHeight ?? 0), behavior: "smooth" }); }}
          tabs={sections.map((s) => ({ id: s.id, label: s.label, count: result ? visible(s).length : undefined }))} />
        {result ? <button className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={() => setPrinting(true)} title="Every section on one page, ready to save as PDF"><FileText size={13} />Report</button> : null}
        <span style={{ marginLeft: result ? 0 : "auto", opacity: stuck ? 1 : 0, transition: "opacity .2s", pointerEvents: stuck ? "auto" : "none" }}>{runButton}</span>
      </div>

      <div style={{ padding: "6px 18px 22px" }}>
        {run.error && !running ? <RunError message={run.error} /> : null}
        {result && printing ? (
          <div className="report">
            {sections.map((sec) => (
              <section key={sec.id} className="out-grid report-sec">
                <h2 className="report-h">{sec.label}</h2>
                {sec.intro ? <div className="section-h"><p>{sec.intro}</p></div> : null}
                {shown(sec).map((item) => (
                  <div key={item.keys.join("+") + (item.view ?? "")} style={{ gridColumn: `span ${item.span}`, minWidth: 0 }}>
                    <OutputCard item={item} feature={feature} result={result} maximized={false} onToggleMax={() => undefined} scope={scope} />
                  </div>
                ))}
              </section>
            ))}
            {result.meta.research_caveats?.length ? <Caveats items={result.meta.research_caveats} /> : null}
          </div>
        ) : result && active ? (
          maxItem ? (
            <motion.div key={`max-${maxKey}`} initial={{ opacity: 0, scale: 0.99 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: DUR.base }}>
              <OutputCard item={{ ...maxItem, span: 12 }} feature={feature} result={result} maximized onToggleMax={() => setMaxKey(null)} scope={scope} />
            </motion.div>
          ) : (
            <motion.div key={`${active.id}-${run.jobId}`} className="out-grid" initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.015 } } }}>
              {active.intro ? <div className="section-h"><p>{active.intro}</p></div> : null}
              {hidden.size && visible(active).some((i) => hidden.has(i.keys[0])) ? (
                <div style={{ gridColumn: "1 / -1" }}><button className="btn sm ghost" onClick={() => setHidden(new Set())}>Show {visible(active).filter((i) => hidden.has(i.keys[0])).length} hidden</button></div>
              ) : null}
              {shown(active).map((item) => (
                <motion.div key={item.keys.join("+") + (item.view ?? "")} style={{ gridColumn: `span ${item.span}`, minWidth: 0 }}
                  variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: [0.2, 0, 0, 1] } } }}>
                  <OutputCard item={item} feature={feature} result={result} maximized={false} onToggleMax={() => setMaxKey(item.keys[0])} onHide={() => setHidden((h) => new Set(h).add(item.keys[0]))} scope={scope} />
                </motion.div>
              ))}
              {result.meta.research_caveats?.length ? <Caveats items={result.meta.research_caveats} /> : null}
            </motion.div>
          )
        ) : (
          <Placeholder items={active?.items ?? []} running={running} onRun={run.run} />
        )}
      </div>
    </div>
  );
}

const CTX: { id: string; label: string; match: (f: InputSpec) => boolean }[] = [
  { id: "period", label: "Period", match: (f) => /lookback|start_date|end_date|period|horizon|window|years/i.test(f.key) },
  { id: "universe", label: "Universe", match: (f) => f.type === "ticker_list" || /^(universe|max_symbols|signal)$/.test(f.key) },
  { id: "costs", label: "Costs", match: (f) => /cost|fee|slippage|bps|turnover/i.test(f.key) },
];

const summarize = (f: InputSpec, v: unknown) => {
  if (v === "" || v === undefined || v === null) return null;
  if (f.key === "max_symbols") return `${v} names`;
  if (f.key === "lookback_days" && isNum(Number(v))) return `${(Number(v) / 365).toFixed(0)}y`;
  if (Array.isArray(v)) return v.map(label).join(", ");
  const t = String(v);
  return t.includes(",") ? `${t.split(",").length} tickers` : typeof v === "boolean" ? (v ? "on" : "off") : label(v);
};

/** Run-context bar: what the shown run used, as chips that open the matching study fields. */
function RunContext({ feature, run }: { feature: FeatureSpec; run: FeatureRun }) {
  const [open, setOpen] = useState<{ id: string; at: MenuAt } | null>(null);
  const groups = CTX.map((g) => ({ ...g, fields: feature.inputs.filter(g.match).slice(0, 5) })).filter((g) => g.fields.length);
  if (!groups.length) return null;
  const cur = groups.find((g) => g.id === open?.id);
  return (
    <div className="ctxbar" style={{ padding: "12px 0 0" }}>
      {groups.map((g) => {
        const text = g.fields.map((f) => summarize(f, run.form[f.key])).filter(Boolean).slice(0, 3).join(" · ") || "Default";
        return (
          <button key={g.id} type="button" className="chip" aria-haspopup="menu" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setOpen({ id: g.id, at: { x: r.left, y: r.bottom + 4 } }); }}>
            <span style={{ color: "var(--text-4)" }}>{g.label}</span>{text}<ChevronDown size={11} />
          </button>
        );
      })}
      {run.stale ? <span className="chip stale" title="The form no longer matches the run on screen">Settings changed, results are stale</span> : null}
      <PopMenu at={open?.at ?? null} onClose={() => setOpen(null)} width={300} sticky>
        <div style={{ display: "grid", gap: 10, padding: 8 }}>
          {cur?.fields.map((f) => (
            <label key={f.key} className="field"><span>{f.label}</span>
              <Control field={f} value={run.form[f.key]} onChange={(v) => run.setForm((c) => ({ ...c, [f.key]: v }))} />
            </label>
          ))}
        </div>
      </PopMenu>
    </div>
  );
}

function VerdictStrip({ feature, result }: { feature: FeatureSpec; result: FeatureResult }) {
  const v = verdictFor(feature, result);
  const cards = (result.summary_cards ?? []).filter((c) => !(typeof c.value === "string" && ["red", "amber", "green"].includes(c.value))).slice(0, 5);
  const color = v.tone === "up" ? "var(--up)" : v.tone === "down" ? "var(--down)" : v.tone === "warn" ? "var(--warn)" : "var(--accent)";
  const [lead, ...rest] = (v.headline ?? "").split(/(?<=\.)\s/);
  return (
    <div className="verdict">
      {v.headline ? (
        <div className="verdict-lead" style={{ background: `color-mix(in oklch, ${color} 7%, var(--panel))`, boxShadow: `inset 0 0 0 1px color-mix(in oklch, ${color} 22%, transparent)` }}>
          <span style={{ width: 8, height: 8, marginTop: 7, borderRadius: 3, background: color, flex: "none", boxShadow: `0 0 0 4px color-mix(in oklch, ${color} 18%, transparent)` }} />
          <p style={{ fontSize: 14, lineHeight: 1.55, color: "var(--text)" }}>
            <b style={{ fontWeight: 600, color }}>{lead}</b>{rest.length ? <span style={{ color: "var(--text-2)" }}> {rest.join(" ")}</span> : null}
          </p>
        </div>
      ) : null}
      {cards.length ? (
        <div className="kpis">
          {cards.map((c) => (
            <div key={c.label} className="kpi">
              <div className="l">{c.label}</div>
              <div className={`v${isNum(c.value) && /return|alpha|sharpe|t-stat|spread|premium/i.test(c.label) && c.value !== 0 ? (c.value > 0 ? " up" : " down") : ""}`}>{isNum(c.value) ? kpi(c.value) : String(c.value)}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Headline numbers: enough precision to see small slopes, never more than four decimals. */
const kpi = (v: number) => (Number.isInteger(v) ? num(v) : Math.abs(v) < 0.1 ? num(v, 4) : Math.abs(v) < 10 ? num(v, 3) : num(v, 1));

function Progress({ startedAt, status }: { startedAt: number | null; status: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(id); }, []);
  const secs = startedAt ? Math.max(0, (now - startedAt) / 1000) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, padding: "10px 14px", borderRadius: 10, background: "var(--panel)", boxShadow: "inset 0 0 0 1px var(--line)", fontSize: 12.5, color: "var(--text-2)" }}>
      <Loader2 size={14} className="spin" style={{ color: "var(--accent)" }} />
      <span>{status === "queued" ? "Queued" : status === "submitting" ? "Submitting the study" : "Estimating"}</span>
      <div className="progress"><i /></div>
      <span className="num" style={{ marginLeft: "auto", color: "var(--text-3)" }}>{secs.toFixed(1)}s</span>
    </div>
  );
}

function Placeholder({ items, running, onRun }: { items: Item[]; running: boolean; onRun: () => void }) {
  return (
    <div style={{ position: "relative" }}>
      <div className="out-grid" aria-hidden style={{ opacity: running ? 1 : 0.4 }}>
        {items.map((i, n) => (
          <div key={i.keys.join("+") + (i.view ?? "")} className="card" style={{ gridColumn: `span ${i.span}`, height: i.span >= 8 ? 320 : 220 }}>
            <div className="card-h"><span className="skel" style={{ width: 110 + (n % 3) * 34, height: 11 }} /></div>
            <div className="card-b">{running ? <span className="skel" style={{ display: "block", height: "100%" }} /> : null}</div>
          </div>
        ))}
      </div>
      {!running ? (
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "start center", paddingTop: 70 }}>
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.base }}
            style={{ textAlign: "center", background: "var(--panel)", padding: "22px 28px", borderRadius: 14, boxShadow: "var(--shadow)", maxWidth: 400 }}>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>Ready when you are</div>
            <div style={{ color: "var(--text-3)", fontSize: 12.5, lineHeight: 1.55, marginBottom: 14 }}>Set the universe, signal and options in the Study panel on the right, then run it. Results appear here section by section.</div>
            <button className="btn primary" onClick={onRun}><Play size={11} fill="currentColor" />Run with these settings<span className="kbd" style={{ background: "transparent", color: "inherit", boxShadow: "none", opacity: 0.55 }}>⌘↵</span></button>
          </motion.div>
        </div>
      ) : null}
    </div>
  );
}

function RunError({ message }: { message: string }) {
  return (
    <div className="card" style={{ height: "auto", marginBottom: 12, background: "var(--down-soft)", boxShadow: "inset 0 0 0 1px color-mix(in oklch, var(--down) 30%, transparent)" }}>
      <div className="card-b" style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <AlertTriangle size={16} style={{ color: "var(--down)", flex: "none", marginTop: 2 }} />
        <div>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>The study could not run</div>
          <div style={{ color: "var(--text-2)", fontSize: 12.5 }}>{message}</div>
        </div>
      </div>
    </div>
  );
}

function Caveats({ items }: { items: string[] }) {
  return (
    <div className="card" style={{ gridColumn: "1 / -1", height: "auto" }}>
      <div className="card-h"><h3>Caveats</h3></div>
      <ul style={{ margin: 0, padding: "8px 14px 14px 32px", color: "var(--text-2)", fontSize: 12.5, lineHeight: 1.65 }}>
        {items.map((c) => <li key={c}>{c}</li>)}
      </ul>
    </div>
  );
}
