"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { TimeSeries } from "@/charts/TimeSeries";
import { openQuickLook } from "@/kit/QuickLook";
import { get } from "@/modules/research/api";
import { featureHref, metaFor } from "@/modules/research/catalog";
import type { RunRecord } from "@/modules/research/types";
import "../filters/universe.css";

export type Tile = { ticker: string; sector: string; band: string | null; market_cap: number | null; r1d: number | null; r1w: number | null; r1m: number | null };
type HistRow = { date: string; advancers: number; decliners: number; new_highs: number; new_lows: number; spy: number | null };

const BANDS = ["Mega", "Large", "Mid", "Small", "Micro"];
const PERIODS = [["r1d", "1D"], ["r1w", "1W"], ["r1m", "1M"]] as const;
const sgn = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
// Diverging tile colour: ±5% (1D) or ±15% (1W/1M) saturates.
const tone = (v: number | null, cap: number) => (v === null ? "var(--raise)" : `color-mix(in oklch, ${v >= 0 ? "var(--up)" : "var(--down)"} ${Math.round(Math.min(1, Math.abs(v) / cap) * 70 + 8)}%, var(--panel))`);

/** Sector rows by market-cap columns; each stock a tile coloured by its change over the chosen period. */
export function GroupMatrix({ tiles }: { tiles: Tile[] }) {
  const [period, setPeriod] = useState<(typeof PERIODS)[number][0]>("r1d");
  const cap = period === "r1d" ? 0.05 : 0.15;
  const sectors = useMemo(() => {
    const by = new Map<string, Tile[]>();
    tiles.forEach((t) => { if (t.band) by.set(t.sector, [...(by.get(t.sector) ?? []), t]); });
    return [...by].map(([s, list]) => [s, list.sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0))] as const).sort((a, b) => b[1].length - a[1].length);
  }, [tiles]);
  const bands = BANDS.filter((b) => tiles.some((t) => t.band === b));
  if (!sectors.length) return null;
  return (
    <div className="gm">
      <div className="gm-bar">
        <div className="ub-seg" role="radiogroup" aria-label="Change over">
          {PERIODS.map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={period === k} onClick={() => setPeriod(k)}>{l}</button>)}
        </div>
      </div>
      <div className="gm-grid" style={{ gridTemplateColumns: `120px repeat(${bands.length}, minmax(0, 1fr))` }}>
        <span />
        {bands.map((b) => <span key={b} className="gm-col">{b}</span>)}
        {sectors.map(([s, list]) => (
          <div key={s} className="gm-row" style={{ display: "contents" }}>
            <span className="gm-sec">{s}</span>
            {bands.map((b) => (
              <div key={b} className="gm-cell">
                {list.filter((t) => t.band === b).map((t) => (
                  <button key={t.ticker} type="button" className="gm-tile" style={{ background: tone(t[period], cap) }} title={`${t.ticker} ${t[period] === null ? "–" : sgn(t[period])}`} onClick={() => openQuickLook(t.ticker)}>{t.ticker}</button>
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Net advancers and net new highs per session, 10-session averages, under SPY. */
export function BreadthHistory() {
  const q = useQuery({ queryKey: ["screener", "breadth-history"], queryFn: () => get<{ rows: HistRow[] }>("/breadth/history"), staleTime: 600_000, retry: false });
  const rows = useMemo(() => {
    const r = q.data?.rows ?? [];
    const avg = (i: number, f: (x: HistRow) => number) => { const w = r.slice(Math.max(0, i - 9), i + 1); return w.reduce((n, x) => n + f(x), 0) / w.length; };
    return r.map((x, i) => ({ date: x.date, spy: x.spy, net: avg(i, (y) => y.advancers - y.decliners), highs: avg(i, (y) => y.new_highs - y.new_lows) }));
  }, [q.data]);
  if (q.isLoading) return <div className="skel-card" style={{ height: 302 }} aria-busy="true" aria-label="Loading breadth history" />;
  if (rows.length < 20) return null;
  return (
    <div className="bh">
      <TimeSeries data={rows} series={[{ key: "spy", label: "SPY" }]} height={120} legend={false} format={(v) => v.toFixed(0)} />
      <TimeSeries data={rows} series={[{ key: "net", label: "Net advancers", kind: "bars" }, { key: "highs", label: "Net new highs" }]} refLines={[{ y: 0 }]} height={150} format={(v) => v.toFixed(0)} />
    </div>
  );
}

/** Last run of each Screener study, with the pass count and its change against the run before. */
export function RecentRuns({ runs }: { runs: RunRecord[] }) {
  const items = useMemo(() => {
    const done = runs.filter((r) => r.status === "completed");
    return [...new Set(done.map((r) => r.featureId))].slice(0, 6).map((id) => {
      const [cur, prev] = done.filter((r) => r.featureId === id);
      const n = cur.metrics?.["After filters"], p = prev?.metrics?.["After filters"];
      return { run: cur, n, delta: n !== undefined && p !== undefined ? n - p : null };
    });
  }, [runs]);
  if (!items.length) return null;
  return (
    <section className="sh-saved">
      {items.map(({ run, n, delta }) => (
        <Link key={run.jobId} href={`${featureHref(run.featureId)}?run=${run.jobId}`} className="sh-screen">
          <span>{metaFor(run.featureId, run.featureName).name}{n !== undefined ? <b className="num"> {n.toLocaleString()}</b> : null}{delta ? <i className={`sh-pill ${delta > 0 ? "green" : "red"}`}>{delta > 0 ? "+" : ""}{delta}</i> : null}</span>
          <small>{run.headline?.split(".")[0] ?? new Date(run.startedAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</small>
        </Link>
      ))}
    </section>
  );
}
