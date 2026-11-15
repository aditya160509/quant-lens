"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { isNum, label, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./story.css";

/** The workspace's Reduce motion switch (.rm): show the end state, never autoplay. */
const still = () => typeof document !== "undefined" && Boolean(document.querySelector(".rm"));

/** A stable shuffle position per dot, so names drop out in a scattered, repeatable order. */
const order = (n: number) => Array.from({ length: n }, (_, i) => i).sort((a, b) => ((a * 2654435761) % 4093) - ((b * 2654435761) % 4093));

/** C2: the universe as dots that drop out filter by filter while the count ticks down to the names that pass. */
export function FunnelStory({ rows, result }: ViewProps) {
  const steps = rows.filter((r) => isNum(r.remaining)) as (Record<string, unknown> & { remaining: number })[];
  const total = steps.length ? steps[0].remaining + (isNum(steps[0].removed) ? steps[0].removed : 0) : 0;
  const per = Math.max(1, Math.ceil(total / 600));
  const dots = Math.ceil(total / per);
  const rank = useMemo(() => { const r = new Array<number>(dots); order(dots).forEach((d, i) => { r[d] = i; }); return r; }, [dots]);
  const names = out(result, "ranked_screener_table").map((r) => String(r.ticker ?? ""));
  const [k, setK] = useState(() => (still() ? steps.length - 1 : -1));
  const [playing, setPlaying] = useState(() => !still());
  useEffect(() => {
    if (!playing) return;
    if (k >= steps.length - 1) { setPlaying(false); return; }
    const id = setTimeout(() => setK((x) => x + 1), k < 0 ? 500 : 1100);
    return () => clearTimeout(id);
  }, [playing, k, steps.length]);
  if (!steps.length) return <Empty />;
  const left = k < 0 ? total : steps[k].remaining;
  const alive = Math.ceil(left / per);
  const worst = Math.max(0, ...steps.map((s) => (isNum(s.removed) ? s.removed : 0)));
  return (
    <div className="fs">
      <div className="fs-top">
        <motion.b key={left} className="num fs-count" initial={still() ? false : { opacity: 0.4, y: -4 }} animate={{ opacity: 1, y: 0 }}>{left.toLocaleString()}</motion.b>
        <span className="fs-of num">of {total.toLocaleString()}</span>
        <span className="fs-now">{k < 0 ? "Every name we hold" : String(steps[k].stage ?? steps[k].key ?? `Step ${k + 1}`)}{k >= 0 && isNum(steps[k].removed) && steps[k].removed ? <em className="num"> −{steps[k].removed.toLocaleString()}</em> : null}</span>
        <button type="button" className="btn sm ghost" onClick={() => { setK(-1); setPlaying(true); }}><RotateCcw size={12} />Replay</button>
      </div>
      <div className="fs-field" role="img" aria-label={`${left.toLocaleString()} of ${total.toLocaleString()} names left`}>
        {rank.map((r, i) => {
          const on = r < alive;
          const end = r < Math.ceil(steps[steps.length - 1].remaining / per);
          const name = per === 1 && end ? names[r] : undefined;
          return name ? <button key={i} type="button" className="fs-dot pass" data-on={on} title={name} onClick={() => openQuickLook(name)} style={{ transitionDelay: `${(r % 60) * 6}ms` }} />
            : <i key={i} className="fs-dot" data-on={on} style={{ transitionDelay: `${(r % 60) * 6}ms` }} />;
        })}
      </div>
      <ol className="fs-steps">
        {steps.map((s, i) => (
          <li key={i} data-at={i === k} data-done={i < k} data-neck={isNum(s.removed) && s.removed > 0 && s.removed === worst}>
            <button type="button" onClick={() => { setPlaying(false); setK(i); }}>{String(s.stage ?? s.key ?? `Step ${i + 1}`)}</button>
            <span className="num">{isNum(s.removed) && s.removed ? `−${s.removed.toLocaleString()}` : ""}</span>
          </li>
        ))}
      </ol>
      {per > 1 ? <p className="fs-note">One dot is {per} names</p> : null}
    </div>
  );
}

type Pt = { date: string; s: number; b: number | null; dd: number };

/** C3: the backtest as it happened: the equity line draws against SPY, drawdowns shade, holdings fly in and out; play or scrub. */
export function BacktestReplay({ result }: ViewProps) {
  const pts = useMemo(() => out(result, "equity_curve").flatMap((r): Pt[] => (typeof r.date === "string" && isNum(r.strategy) ? [{ date: r.date.slice(0, 10), s: r.strategy, b: isNum(r.benchmark) ? r.benchmark : null, dd: isNum(r.drawdown) ? r.drawdown : 0 }] : [])), [result]);
  const log = out(result, "position_entry_exit_log");
  const n = pts.length;
  const [i, setI] = useState(() => (still() ? Math.max(0, n - 1) : 0));
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    if (i >= n - 1) { setPlaying(false); return; }
    // About twelve seconds for the whole run, whatever its length.
    const id = setTimeout(() => setI((x) => Math.min(n - 1, x + Math.max(1, Math.round(n / 400)))), 30);
    return () => clearTimeout(id);
  }, [playing, i, n]);
  const geo = useMemo(() => {
    if (n < 2) return null;
    const vals = pts.flatMap((p) => [p.s, ...(p.b === null ? [] : [p.b])]);
    const lo = Math.min(...vals), hi = Math.max(...vals), minDd = Math.min(-0.01, ...pts.map((p) => p.dd));
    const x = (k: number) => (k / (n - 1)) * 1000;
    const y = (v: number) => 220 - ((v - lo) / (hi - lo || 1)) * 205;
    const yd = (v: number) => 240 + (v / minDd) * 58;
    return { x, y, yd };
  }, [pts, n]);
  if (!geo) return <Empty />;
  const cut = pts.slice(0, i + 1);
  const line = (key: "s" | "b") => cut.map((p, k) => (p[key] === null ? "" : `${k ? "L" : "M"}${geo.x(k).toFixed(1)},${geo.y(p[key] as number).toFixed(1)}`)).join("");
  const area = `M0,240 ${cut.map((p, k) => `L${geo.x(k).toFixed(1)},${geo.yd(p.dd).toFixed(1)}`).join(" ")} L${geo.x(i).toFixed(1)},240 Z`;
  const now = pts[i], first = pts[0];
  const held = log.filter((r) => typeof r.entry_date === "string" && r.entry_date.slice(0, 10) <= now.date && !(typeof r.exit_date === "string" && r.exit_date.slice(0, 10) <= now.date)).map((r) => String(r.ticker));
  const sr = now.s / first.s - 1, br = now.b !== null && first.b ? now.b / first.b - 1 : null;
  const sign = (v: number) => `${v > 0 ? "+" : ""}${pct(v, 1)}`;
  return (
    <div className="br">
      <div className="br-top">
        <button type="button" className="btn sm primary" onClick={() => { if (i >= n - 1) setI(0); setPlaying((p) => !p); }} aria-label={playing ? "Pause" : "Play"}>{playing ? <Pause size={12} /> : <Play size={12} fill="currentColor" />}{playing ? "Pause" : i >= n - 1 ? "Replay" : "Play"}</button>
        <span className="br-date num">{now.date}</span>
        <span className="br-fig num" style={{ color: br === null || sr >= br ? "var(--up)" : "var(--down)" }}>{sign(sr)}</span>
        {br !== null ? <span className="br-sub num">SPY {sign(br)}</span> : null}
        <span className="br-sub num">drawdown {pct(now.dd, 1)}</span>
      </div>
      <svg className="br-plot" viewBox="0 0 1000 300" preserveAspectRatio="none" role="img" aria-label={`Strategy ${sign(sr)} against SPY on ${now.date}`}>
        <line x1={0} x2={1000} y1={240} y2={240} stroke="var(--grid)" vectorEffect="non-scaling-stroke" />
        <path d={area} fill="color-mix(in oklch, var(--down) 28%, transparent)" />
        <path d={line("b")} fill="none" stroke="var(--text-3)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
        <path d={line("s")} fill="none" stroke="var(--accent)" strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        <line x1={geo.x(i)} x2={geo.x(i)} y1={0} y2={300} stroke="var(--line-3)" vectorEffect="non-scaling-stroke" />
      </svg>
      <input className="br-scrub" type="range" min={0} max={n - 1} value={i} aria-label="Date" onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} />
      <div className="br-held" aria-live="off">
        <span className="br-sub">{held.length} held</span>
        <AnimatePresence initial={false} mode="popLayout">
          {held.map((t) => (
            <motion.button key={t} type="button" layout className="chip" onClick={() => openQuickLook(t)}
              initial={{ opacity: 0, y: -10, scale: 0.8 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.8 }} transition={{ duration: still() ? 0 : 0.18 }}>{t}</motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

const FIELD_METRICS = ["core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile"];

/** C5: every name a bubble sized by market cap, grouped by sector, height = the chosen score. Raise the bar and failing names sink and fade; the strongest rise. */
export function SortingField({ rows }: ViewProps) {
  const [metric, setMetric] = useState(FIELD_METRICS[0]);
  const [min, setMin] = useState(0);
  const names = useMemo(() => rows.filter((r) => typeof r.ticker === "string").slice(0, 600), [rows]);
  const sectors = useMemo(() => [...new Set(names.map((r) => (typeof r.sector === "string" && r.sector ? r.sector : "Unknown")))].sort(), [names]);
  const caps = names.map((r) => (isNum(r.market_cap) && r.market_cap > 0 ? r.market_cap : 0));
  const top = Math.max(1, ...caps);
  const vals = names.map((r) => (isNum(r[metric]) ? (r[metric] as number) : null));
  const passing = vals.filter((v) => v !== null && v >= min).length;
  const cut90 = [...vals].filter((v): v is number => v !== null && v >= min).sort((a, b) => b - a)[Math.max(0, Math.floor(passing * 0.1) - 1)] ?? Infinity;
  if (!names.length) return <Empty />;
  return (
    <div className="sf">
      <div className="sf-bar">
        <select className="cmp-select" value={metric} onChange={(e) => setMetric(e.target.value)} aria-label="Score">{FIELD_METRICS.map((m) => <option key={m} value={m}>{label(m)}</option>)}</select>
        <label className="sf-min"><span>At least</span><input type="range" min={0} max={95} step={5} value={min} onChange={(e) => setMin(Number(e.target.value))} aria-label="Minimum score" /><b className="num">{min}</b></label>
        <span className="sf-count"><b className="num">{passing.toLocaleString()}</b> of {names.length.toLocaleString()} pass</span>
      </div>
      <div className="sf-field" role="img" aria-label={`${passing} of ${names.length} names score at least ${min} on ${label(metric)}`}>
        {sectors.map((sec, i) => <span key={sec} className="sf-sec" style={{ left: `${((i + 0.5) / sectors.length) * 100}%` }}>{sec}</span>)}
        {names.map((r, i) => {
          const v = vals[i];
          const pass = v !== null && v >= min;
          const band = sectors.indexOf(typeof r.sector === "string" && r.sector ? r.sector : "Unknown");
          const jitter = (((i * 2654435761) % 1000) / 1000) * 0.8 + 0.1;
          const size = 6 + Math.sqrt(caps[i] / top) * 30;
          const t = String(r.ticker);
          return (
            <button key={t} type="button" className="sf-dot" data-pass={pass} data-top={pass && v !== null && v >= cut90} title={`${t} ${v === null ? "unknown" : v.toFixed(0)}`} onClick={() => openQuickLook(t)}
              style={{ left: `${((band + jitter) / sectors.length) * 100}%`, top: `${pass ? 96 - (((v as number) - min) / Math.max(1, 100 - min)) * 90 : 100}%`, width: size, height: size, transitionDelay: `${(i % 40) * 4}ms` }} />
          );
        })}
      </div>
    </div>
  );
}
