"use client";

import { useScreenerPalette } from "../palette";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Search, Bell, FlaskConical, Gem, HeartPulse, Rocket, ShieldCheck, Sparkles, Trophy, Wallet, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BreadthHistory, GroupMatrix, RecentRuns, type Tile } from "./OverviewCharts";
import { get, latestRun } from "@/modules/research/api";
import { featureHref, metaFor } from "@/modules/research/catalog";
import { useStudies } from "@/modules/research/store";
import { Treemap } from "@/charts/Treemap";
import { defaultsFor } from "@/modules/research/StudyForm";
import type { FeatureSpec, RunRecord } from "@/modules/research/types";
import "./home.css";

type Template = { key: string; formula: string; weak_evidence: boolean };
type Facet = { name: string; count: number };
type Breadth = { universe: number; advancers: number; decliners: number; unchanged: number; near_high: number; near_low: number; median_1d: number | null; sectors: { sector: string; median_1m: number; count: number; market_cap?: number }[]; tiles?: Tile[] };
// The shell opens its search on "/"; a synthetic key on the body reuses that one entry point.
const openSearch = () => document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }));
const sgn = (v: number, d = 1) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;

const THEMES: { label: string; hue: number; icon: LucideIcon; keys: string[] }[] = [
  { label: "Value", hue: 258, icon: Gem, keys: ["deep_value", "cheap_high_fscore", "below_book_liquid", "large_cap_value", "low_pe_growth", "cheap_and_improving"] },
  { label: "Quality", hue: 157, icon: ShieldCheck, keys: ["quality_compounders", "high_roic_high_earnings_yield", "fcf_machines", "mega_cap_quality", "quiet_compounders", "profitable_small_caps"] },
  { label: "Growth", hue: 300, icon: Rocket, keys: ["growth_at_a_reasonable_price", "high_roic_growth", "earnings_turnaround", "sales_acceleration"] },
  { label: "Income", hue: 75, icon: Wallet, keys: ["dividend_income", "shareholder_yield", "defensive_dividend_growers"] },
  { label: "Momentum", hue: 30, icon: Sparkles, keys: ["momentum_leaders", "breakout_52w", "uptrend_above_averages", "golden_cross_recent", "volume_surge"] },
  { label: "Defensive", hue: 195, icon: HeartPulse, keys: ["low_volatility", "safe_balance_sheet", "oversold_quality", "beaten_down_quality"] },
];

const WORK: { id: string; hue: number; icon: LucideIcon }[] = [
  { id: "sc03", hue: 75, icon: Trophy },
  { id: "sc05", hue: 300, icon: FlaskConical },
  { id: "sc06", hue: 30, icon: Bell },
];

const title = (key: string) => key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()).replace(/\broic\b/gi, "ROIC").replace(/\bfcf\b/gi, "FCF").replace(/\bfscore\b/gi, "F-score").replace(/\b52w\b/gi, "52-week").replace(/\bpe\b/gi, "P/E");
const terms = (formula: string) => formula.split(/\s+and\s+/).map((t) => t.replace(/_/g, " ").replace(/\s*(>=|<=|=)\s*/, " $1 ")).slice(0, 3);
const ago = (t: number) => { const m = Math.round((Date.now() - t) / 60000); return m < 60 ? `${Math.max(m, 1)}m` : m < 2880 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`; };

export function ScreenerHome({ features, runs }: { features: FeatureSpec[]; runs: RunRecord[] }) {
  const router = useRouter();
  useScreenerPalette();
  const [sizeBy, setSizeBy] = useState<"names" | "cap">("cap");
  const templates = useQuery({ queryKey: ["screener", "templates"], queryFn: () => get<{ templates: Template[] }>("/templates"), staleTime: Infinity, retry: false });
  const facets = useQuery({ queryKey: ["screener", "facets"], queryFn: () => get<{ sector: Facet[] }>("/facets"), staleTime: 600_000, retry: false });
  const breadth = useQuery({ queryKey: ["screener", "breadth"], queryFn: () => get<Breadth>("/breadth"), staleTime: 600_000, retry: false }).data;
  const saved = useQuery({ queryKey: ["screener", "screens"], queryFn: () => get<{ screens: { screen_id: string; name: string; feature_id: string; payload: Record<string, unknown> }[] }>("/screens"), retry: false }).data?.screens ?? [];
  const byKey = new Map((templates.data?.templates ?? []).map((t) => [t.key, t]));
  const sectors = (facets.data?.sector ?? []).filter((s) => s.name && s.name !== "Unknown");
  const names = sectors.reduce((n, s) => n + s.count, 0);
  const top = sectors[0]?.count ?? 1;

  const screen = latestRun(runs, "sc01");
  const passed = screen?.metrics?.["After filters"];
  const loaded = screen?.metrics?.["Universe loaded"];
  const ready = screen?.metrics?.["Valuation-ready stocks"];
  const done = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "failed").length;
  const open = (id: string, patch: Record<string, unknown>) => {
    const f = features.find((x) => x.id === id);
    if (!f) return;
    useStudies.getState().setForm(id, (cur) => ({ ...cur, ...patch }), defaultsFor(f));
    router.push(`${featureHref(id)}?go=1`);
  };

  return (
    <div className="island sh">
      <div className="sh-in">
        <header className="sh-head">
          <h1>Screener</h1>
          <Link href={featureHref("sc01")} className="btn primary">New screen</Link>
        </header>

        <button type="button" className="sh-search" onClick={openSearch}><Search size={16} aria-hidden /><span>Search any stock, screen or formula</span><kbd className="kbd">/</kbd></button>

        {breadth ? (
          <section className="sh-breadth" aria-label="Market breadth">
            <div className="sh-adv">
              <div className="sh-l"><span>Advancers</span><em>{breadth.universe} names</em></div>
              <div className="sh-ad-bar"><i className="up" style={{ flex: breadth.advancers }} /><i style={{ flex: breadth.unchanged }} /><i className="down" style={{ flex: breadth.decliners }} /></div>
              <div className="sh-ad-n num"><b className="up">{breadth.advancers}</b><span>{breadth.median_1d !== null ? `median ${sgn(breadth.median_1d, 2)}` : ""}</span><b className="down">{breadth.decliners}</b></div>
            </div>
            <div className="sh-hl"><div className="sh-l"><span>Near 52-week high</span></div><b className="num up">{breadth.near_high}</b></div>
            <div className="sh-hl"><div className="sh-l"><span>Near 52-week low</span></div><b className="num down">{breadth.near_low}</b></div>
            <div className="sh-secret">
              <div className="sh-l"><span>Sectors, 1 month</span></div>
              <div className="sh-sr">{breadth.sectors.map((x) => <button key={x.sector} type="button" title={`${x.sector}: ${sgn(x.median_1m)} median, ${x.count} names`} className={x.median_1m >= 0 ? "up" : "down"} style={{ ["--a" as string]: `${Math.min(60, Math.abs(x.median_1m) * 400)}%` }} onClick={() => open("sc01", { sector: x.sector })}><span>{x.sector}</span><b className="num">{sgn(x.median_1m)}</b></button>)}</div>
            </div>
          </section>
        ) : null}

        {breadth?.sectors.length ? (
          <section className="sh-tree">
            <div className="ub-seg sh-size" role="radiogroup" aria-label="Size by">
              {([["cap", "Market cap"], ["names", "Names"]] as const).map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={sizeBy === k} onClick={() => setSizeBy(k)}>{l}</button>)}
            </div>
            <Treemap title={`Sectors by ${sizeBy === "cap" ? "market cap" : "names"}, coloured by 1-month median return`} sizeLabel={sizeBy === "cap" ? "Market cap" : "Names"} colorLabel="Median 1M return" colorAggregate="mean"
              format={(v) => (sizeBy === "cap" ? `$${(v / 1e12).toFixed(2)}T` : v.toFixed(0))} colorFormat={(v) => sgn(v)}
              items={breadth.sectors.map((x) => ({ label: x.sector, group: x.sector, size: sizeBy === "cap" ? x.market_cap ?? 0 : x.count, colorValue: x.median_1m }))} onFilterGroup={(g) => open("sc01", { sector: g })} />
          </section>
        ) : null}

        {breadth?.tiles?.length ? (
          <>
            <h2 className="sh-h">Sectors by size</h2>
            <GroupMatrix tiles={breadth.tiles} />
          </>
        ) : null}

        {breadth ? (
          <>
            <h2 className="sh-h">Breadth, 1 year</h2>
            <BreadthHistory />
          </>
        ) : null}

        <section className="sh-stats">
          <Stat label="Last screen" value={passed !== undefined ? passed.toLocaleString() : "–"} tag={screen ? ago(screen.startedAt) : undefined}>
            {passed !== undefined && loaded ? <div className="sh-bar"><i style={{ width: `${(passed / loaded) * 100}%` }} /></div> : null}
          </Stat>
          <Stat label="Valuation ready" value={ready !== undefined ? ready.toLocaleString() : "–"}>
            {ready !== undefined && loaded ? <div className="sh-bar g"><i style={{ width: `${(ready / loaded) * 100}%` }} /></div> : null}
          </Stat>
          <Stat label="Stocks covered" value={names ? names.toLocaleString() : "–"}>
            <div className="sh-mini">{sectors.slice(0, 11).map((s) => <i key={s.name} style={{ height: `${Math.max(12, (s.count / top) * 100)}%` }} />)}</div>
          </Stat>
          <Stat label="Runs" value={done.toLocaleString()}>
            <div className="sh-pills">{failed ? <span className="sh-pill red">{failed} failed</span> : null}<span className="sh-pill green">{done} done</span></div>
          </Stat>
        </section>

        <section className="sh-work">
          {WORK.map(({ id, hue, icon: Icon }) => {
            const m = metaFor(id);
            const run = latestRun(runs, id);
            return (
              <Link key={id} href={featureHref(id)} className="sh-tile" style={{ ["--h" as string]: hue }}>
                <span className="sh-ic"><Icon size={16} /></span>
                <b>{m.name}</b>
                {run ? <span className={`sh-pill ${run.status === "failed" ? "red" : run.status === "completed" ? "green" : "amber"}`}>{run.status}</span> : null}
                <ArrowUpRight size={14} />
              </Link>
            );
          })}
        </section>

        {runs.some((r) => r.status === "completed") ? <><h2 className="sh-h">Recent</h2><RecentRuns runs={runs} /></> : null}

        {saved.length ? (
          <>
            <h2 className="sh-h">Your screens <Link href="/screener/saved" className="sh-more">All</Link></h2>
            <section className="sh-saved">
              {saved.slice(-6).reverse().map((x) => (
                <button key={x.screen_id} type="button" className="sh-screen" onClick={() => open(`sc${x.feature_id}`, x.payload)}>
                  <span>{x.name}</span>
                  <small>{metaFor(`sc${x.feature_id}`).name}</small>
                </button>
              ))}
            </section>
          </>
        ) : null}

        <h2 className="sh-h">Screens</h2>
        <section className="sh-themes">
          {THEMES.map(({ label, hue, icon: Icon, keys }) => (
            <div key={label} className="sh-theme" style={{ ["--h" as string]: hue }}>
              <div className="sh-theme-h"><span className="sh-ic"><Icon size={15} /></span><b>{label}</b><em>{keys.filter((k) => byKey.has(k)).length}</em></div>
              {keys.map((k) => byKey.get(k)).filter((t): t is Template => Boolean(t)).map((t) => (
                <button key={t.key} type="button" className="sh-screen" title={t.formula} onClick={() => open("sc02", { formula: t.formula })}>
                  <span>{title(t.key)}{t.weak_evidence ? <i className="sh-pill amber">Weak</i> : null}</span>
                  <small>{terms(t.formula).join("  ·  ")}</small>
                </button>
              ))}
            </div>
          ))}
        </section>

        <h2 className="sh-h">Sectors</h2>
        <section className="sh-sectors">
          {sectors.map((s) => (
            <button key={s.name} type="button" className="sh-sector" onClick={() => open("sc01", { sector: s.name })}>
              <i style={{ width: `${(s.count / top) * 100}%` }} />
              <span>{s.name}</span><b className="num">{s.count.toLocaleString()}</b>
            </button>
          ))}
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value, tag, children }: { label: string; value: string; tag?: string; children?: React.ReactNode }) {
  return (
    <div className="sh-stat">
      <div className="sh-l"><span>{label}</span>{tag ? <em>{tag}</em> : null}</div>
      <div className="sh-v">{value}</div>
      <div className="sh-g">{children}</div>
    </div>
  );
}
