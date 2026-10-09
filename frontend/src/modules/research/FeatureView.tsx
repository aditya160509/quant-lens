"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ChevronDown, FileText, Loader2, Play, Square } from "lucide-react";
import { DUR } from "@/workspace/prefs";
import { PopMenu, Tabs, type MenuAt } from "@/workspace/ui";
import { featureHref, metaFor, pageOf } from "./catalog";
import { lab, runLabel } from "./lab";
import { LedgerChip } from "./Projects";
import { useActiveSignal } from "./api";
import { isNum, label, num, out } from "./format";
import { layoutFor, verdictFor, type Item, type Section } from "./layouts";
import { arrange, cardId, useCardPrefs, useFeaturePrefs } from "./cardPrefs";
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
  const prefs = useFeaturePrefs(feature.id);
  const setPref = useCardPrefs((st) => st.set);
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
  const visible = (s: Section) => (result ? s.items.filter((i) => i.keys.some((k) => out(result, k).length > 0) && !repeatsKpis(result, i)) : s.items);
  const shown = (s: Section) => arrange(visible(s), prefs);
  const hiddenIn = (s: Section) => visible(s).filter((i) => prefs[cardId(i)]?.hidden);
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

  // [ and ] step through the section tabs, outside text fields.
  const sectionIds = sections.map((x) => x.id).join(",");
  useEffect(() => {
    const ids = sectionIds.split(",").filter(Boolean);
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || !ids.length || (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))) return;
      if (e.key !== "[" && e.key !== "]") return;
      e.preventDefault();
      setTab((cur) => { const i = Math.max(0, ids.indexOf(cur)); return ids[(i + (e.key === "]" ? 1 : ids.length - 1)) % ids.length]; });
      setMaxKey(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sectionIds]);

  const scope = `${feature.id}:${run.jobId ?? "draft"}`;
  const maxItem = maxKey && active ? active.items.find((i) => i.keys[0] === maxKey) : null;

  const runButton = (
    <div className="fv-run">
      {running && run.status !== "submitting" ? <button className="btn" onClick={run.cancel}><Square size={11} />Cancel</button> : null}
      <button className="btn primary" onClick={run.run} disabled={running} title={`${runLabel(feature.id)} (⌘↵)`}>
        {running ? <Loader2 size={13} className="spin" /> : <Play size={11} fill="currentColor" />}
        {running ? "Running" : result ? "Run again" : runLabel(feature.id)}
        <span className="kbd" style={{ background: "transparent", color: "inherit", boxShadow: "none", opacity: 0.55 }}>⌘↵</span>
      </button>
    </div>
  );

  return (
    <div ref={scroller} className="island results" data-lab={lab().id} style={{ overflowY: "auto", overflowX: "hidden" }}>
      <div ref={hero} style={{ padding: "22px 22px 6px" }}>
        <PageSwitch featureId={feature.id} />
        <div className="fv-head">
          <div className="ov-icon" style={{ width: 40, height: 40, borderRadius: 11 }}><Icon size={19} strokeWidth={1.6} /></div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.2 }}>{meta.name}</h1>
            <p style={{ marginTop: 4, color: "var(--text-2)", fontSize: 13.5 }}>{meta.question}</p>
            <p style={{ marginTop: 6, color: "var(--text-3)", fontSize: 12.5, maxWidth: 860, lineHeight: 1.55 }}>{feature.description}</p>
          </div>
          {runButton}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <RunContext feature={feature} run={run} />
          {lab().signal ? <><ActiveSignalChip /><LedgerChip /></> : null}
        </div>
        <AnimatePresence initial={false}>
          {result ? (
            <motion.div key={run.jobId ?? "r"} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.slow, ease: [0.2, 0, 0, 1] }}>
              <VerdictStrip feature={feature} result={result} />
            </motion.div>
          ) : null}
        </AnimatePresence>
        {running ? <Progress startedAt={run.startedAt} status={run.status} progress={run.progress} /> : null}
      </div>

      <div className={`sticky-bar${stuck ? " stuck" : ""}`}>
        <span className="sticky-title"><Icon size={14} strokeWidth={1.7} style={{ color: "var(--accent)" }} />{meta.name}<span style={{ color: "var(--line-3)" }}>/</span></span>
        <Tabs value={active?.id ?? ""} onChange={(id) => { setTab(id); setMaxKey(null); scroller.current?.scrollTo({ top: Math.min(scroller.current.scrollTop, hero.current?.offsetHeight ?? 0), behavior: "smooth" }); }}
          tabs={sections.map((s) => ({ id: s.id, label: s.label, count: result ? visible(s).length : undefined }))} />
        {result ? <button className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={() => setPrinting(true)} title="Every section on one page, ready to save as PDF"><FileText size={13} />Report</button> : null}
        <span className="sticky-run" style={{ marginLeft: result ? 0 : "auto" }} aria-hidden={!stuck} inert={!stuck}>{runButton}</span>
      </div>

      <div style={{ padding: "6px 18px 22px" }}>
        {run.error && !running ? <RunError message={run.error} /> : null}
        {result && !running ? <Skipped result={result} /> : null}
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
              {hiddenIn(active).length ? (
                <div style={{ gridColumn: "1 / -1" }}><button className="btn sm ghost" onClick={() => hiddenIn(active).forEach((i) => setPref(feature.id, cardId(i), { hidden: false }))}>Show {hiddenIn(active).length} hidden</button></div>
              ) : null}
              {shown(active).map((item) => (
                <motion.div key={item.keys.join("+") + (item.view ?? "")} style={{ gridColumn: `span ${item.span}`, minWidth: 0 }}
                  variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: [0.2, 0, 0, 1] } } }}>
                  <OutputCard item={item} feature={feature} result={result} maximized={false} onToggleMax={() => setMaxKey(item.keys[0])} onHide={() => setPref(feature.id, cardId(item), { hidden: true })}
                    onMove={(d) => { const list = shown(active); const i = list.findIndex((x) => cardId(x) === cardId(item)); const j = i + d; if (j < 0 || j >= list.length) return; list.forEach((x, k) => setPref(feature.id, cardId(x), { order: k === i ? j : k === j ? i : k })); }}
                    onSpan={(span) => setPref(feature.id, cardId(item), { span })} scope={scope} />
                </motion.div>
              ))}
              {result.meta.research_caveats?.length ? <Caveats items={result.meta.research_caveats} /> : null}
            </motion.div>
          )
        ) : (
          <Placeholder items={active?.items ?? []} running={running} onRun={run.run} featureId={feature.id} />
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
        const tickers = g.fields.find((f) => f.type === "ticker_list");
        const defaultUniverse = g.id === "universe" && tickers && !String(run.form[tickers.key] ?? "").trim() ? lab().defaultUniverse : undefined;
        const text = defaultUniverse ?? (g.fields.map((f) => summarize(f, run.form[f.key])).filter(Boolean).slice(0, 3).join(" · ") || "Default");
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
        <div className="verdict-lead" style={{ ["--tone" as string]: color }}>
          {lab().id === "ml" && STAMP[v.tone ?? ""] ? <span className="verdict-stamp">{STAMP[v.tone ?? ""]}</span> : null}
          <p><b>{lead}</b>{rest.length ? <> {rest.join(" ")}</> : null}</p>
        </div>
      ) : null}
      {lab().signal && explain(cards).length ? <p className="verdict-explain">{explain(cards).join(" ")}</p> : null}
      {cards.length ? (
        <div className="kpis">
          {cards.map((c) => (
            <div key={c.label} className="kpi">
              <div className="l" title={c.label}>{c.label}</div>
              <div className={`v${isNum(c.value) ? "" : " word"}${isNum(c.value) && /return|alpha|sharpe|t-stat|spread|premium/i.test(c.label) && c.value !== 0 ? (c.value > 0 ? " up" : " down") : ""}`}>{isNum(c.value) && UNIT_FMT[c.unit ?? ""] ? UNIT_FMT[c.unit ?? ""](c.value) : isNum(c.value) ? kpi(c.value) : typeof c.value === "string" && /^[a-z][a-z0-9_]*$/.test(c.value) ? label(c.value) : String(c.value)}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** The stamp over a verdict: what the colour means, in a word, for labs that judge (ML). */
const STAMP: Record<string, string> = { up: "Held up", warn: "Mixed", down: "Failed" };

/** Units the API states explicitly are formatted as such; anything else falls back to kpi(). */
const UNIT_FMT: Record<string, (v: number) => string> = {
  "%": (v) => (v === 0 ? "0%" : `${(v * 100).toFixed(Math.abs(v) < 0.1 ? 2 : 1)}%`),
  "×": (v) => `${v.toFixed(2)}×`,
  "Δ Sharpe": (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`,
  days: (v) => `${Math.round(v)} days`,
};

/** Headline numbers: enough precision to see small slopes, never more than four decimals. */
const kpi = (v: number) => (Number.isInteger(v) ? num(v) : Math.abs(v) < 0.1 ? num(v, 4) : Math.abs(v) < 10 ? num(v, 3) : num(v, 1));

/** Elapsed time, plus the stage and percent when the API reports them ({ percent, message }). */
function Progress({ startedAt, status, progress }: { startedAt: number | null; status: string; progress?: unknown }) {
  const p = progress && typeof progress === "object" ? progress as { percent?: number; message?: string } : null;
  const percent = typeof p?.percent === "number" ? Math.max(0, Math.min(100, p.percent)) : null;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(id); }, []);
  const secs = startedAt ? Math.max(0, (now - startedAt) / 1000) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, padding: "10px 14px", borderRadius: 10, background: "var(--panel)", boxShadow: "inset 0 0 0 1px var(--line)", fontSize: 12.5, color: "var(--text-2)" }}>
      <Loader2 size={14} className="spin" style={{ color: "var(--accent)" }} />
      <span>{status === "queued" ? "Queued" : status === "submitting" ? "Submitting the study" : p?.message || "Estimating"}</span>
      <div className="progress">{percent !== null && percent > 0 ? <i style={{ animation: "none", width: `${percent}%`, transition: "width .4s var(--ease)" }} /> : <i />}</div>
      {percent !== null && percent > 0 ? <span className="num" style={{ color: "var(--text-3)" }}>{Math.round(percent)}%</span> : null}
      <span className="num" style={{ marginLeft: "auto", color: "var(--text-3)" }}>{secs.toFixed(1)}s</span>
    </div>
  );
}

function Placeholder({ items, running, onRun, featureId }: { items: Item[]; running: boolean; onRun: () => void; featureId: string }) {
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
            <div style={{ color: "var(--text-3)", fontSize: 12.5, lineHeight: 1.55, marginBottom: 14 }}>{lab().emptyHint?.(featureId) ?? "Set the universe, signal and options in the Study panel on the right, then run it. Results appear here section by section."}</div>
            <button className="btn primary" onClick={onRun}><Play size={11} fill="currentColor" />{lab().runLabel ? runLabel(featureId) : "Run with these settings"}<span className="kbd" style={{ background: "transparent", color: "inherit", boxShadow: "none", opacity: 0.55 }}>⌘↵</span></button>
          </motion.div>
        </div>
      ) : null}
    </div>
  );
}

/** Designs or tests the backend skipped, with its reason: e.g. an event study without an event file. */
function Skipped({ result }: { result: FeatureResult }) {
  const rows = Object.values(result.tables ?? {}).flat()
    .filter((r): r is Record<string, unknown> => Boolean(r) && typeof r === "object" && /not run|skipped/i.test(String((r as Record<string, unknown>).status ?? "")) && Boolean((r as Record<string, unknown>).reason));
  if (!rows.length) return null;
  return (
    <div className="card" style={{ height: "auto", marginBottom: 12, background: "var(--warn-soft)", boxShadow: "inset 0 0 0 1px color-mix(in oklch, var(--warn) 30%, transparent)" }}>
      <div className="card-b" style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <AlertTriangle size={16} style={{ color: "var(--warn)", flex: "none", marginTop: 2 }} />
        <div style={{ display: "grid", gap: 4 }}>
          <div style={{ fontWeight: 600 }}>{rows.length === 1 ? "One part did not run" : `${rows.length} parts did not run`}</div>
          {rows.map((r, i) => (
            <div key={i} style={{ color: "var(--text-2)", fontSize: 12.5 }}>
              <b style={{ fontWeight: 500, color: "var(--text)" }}>{label(String(r.design ?? r.test ?? r.name ?? "Step"))}:</b> {String(r.reason)}
            </div>
          ))}
        </div>
      </div>
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

/** The tests that share this page, as pills: one question, several ways to answer it. */
function PageSwitch({ featureId }: { featureId: string }) {
  const page = pageOf(featureId);
  if (!page || page.features.length < 2) return null;
  return (
    <div className="page-switch" role="tablist" aria-label={page.label}>
      <span className="pg">{page.label}</span>
      {page.features.map((id) => (
        <Link key={id} href={featureHref(id)} role="tab" aria-selected={id === featureId} className="pill">{metaFor(id).name}</Link>
      ))}
    </div>
  );
}

/** When a formula from the Signal page is in use, say so: it replaces the page's own signal setting. */
function ActiveSignalChip() {
  const { expr, name, set } = useActiveSignal();
  if (!expr) return null;
  return (
    <span className="chip accent" title={expr} style={{ gap: 6 }}>
      <Link href={`${lab().root}/signal`} style={{ color: "inherit", textDecoration: "none" }}>Signal: {name ?? "formula"}</Link>
      <button aria-label="Use the built-in signal instead" onClick={() => set({ expr: null, name: null })} style={{ display: "grid", placeItems: "center" }}>×</button>
    </span>
  );
}

/** A one-row output whose every number already sits in the key stats strip adds nothing; leave it out. */
function repeatsKpis(result: FeatureResult, item: Item): boolean {
  if (item.keys.length !== 1 || item.view) return false;
  const rows = out(result, item.keys[0]);
  if (rows.length !== 1) return false;
  const shown = new Set((result.summary_cards ?? []).map((c) => (isNum(c.value) ? Number(c.value.toPrecision(6)) : null)).filter((v): v is number => v !== null));
  const nums = Object.values(rows[0]).filter(isNum).map((v) => Number(v.toPrecision(6)));
  return nums.length > 0 && nums.length <= 4 && nums.every((v) => shown.has(v));
}

/**
 * What the headline numbers mean, in words, from fixed templates (no model): t-statistics against
 * the usual and factor-zoo hurdles, p-values against 5%, Sharpe ratios against costs-free noise.
 */
function explain(cards: { label: string; value: unknown }[]): string[] {
  const out: string[] = [];
  const t = cards.find((c) => /t[- ]?stat|\bt\b/i.test(c.label) && isNum(c.value));
  if (t && isNum(t.value)) {
    const a = Math.abs(t.value);
    out.push(a >= 3 ? `A t-statistic of ${t.value.toFixed(2)} clears even the factor-zoo hurdle of 3.` : a >= 2 ? `A t-statistic of ${t.value.toFixed(2)} is significant at 5% on its own, but below the factor-zoo hurdle of 3 that applies after many tried signals.` : `A t-statistic of ${t.value.toFixed(2)} is within what chance alone produces; it is not evidence of a premium.`);
  }
  const p = cards.find((c) => /\bp\b|p-value|p value/i.test(c.label) && isNum(c.value));
  if (p && isNum(p.value)) out.push(p.value < 0.05 ? `${p.label} of ${p.value.toFixed(3)} rejects the null at 5%.` : `${p.label} of ${p.value.toFixed(3)} does not reject the null at 5%.`);
  return out.slice(0, 2);
}
