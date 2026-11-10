"use client";

import { useState } from "react";
import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { first, fmtKey, isNum, label } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./valuation.css";

const DIMS: [string, string][] = [["own_history_percentile", "vs own history"], ["sector_percentile", "vs sector"], ["peer_percentile", "vs peers"], ["universe_percentile", "vs universe"]];

/** Half-circle gauge for a 0 to 100 percentile; unknown draws an empty track. */
function Gauge({ value, title }: { value: unknown; title: string }) {
  const v = isNum(value) ? Math.max(0, Math.min(100, value)) : null;
  const a = Math.PI * (1 - (v ?? 0) / 100);
  const x = 50 + Math.cos(a) * 38, y = 46 - Math.sin(a) * 38;
  return (
    <figure className="vg">
      <svg viewBox="0 0 100 54" role="img" aria-label={`${title}: ${v === null ? "unknown" : `${v.toFixed(0)}th percentile`}`}>
        <path d="M12 46 A38 38 0 0 1 88 46" fill="none" stroke="var(--line)" strokeWidth={7} strokeLinecap="round" />
        {v !== null ? <path d={`M12 46 A38 38 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}`} fill="none" stroke="var(--accent)" strokeWidth={7} strokeLinecap="round" /> : null}
        <text x={50} y={44} textAnchor="middle" fontSize={15} fontWeight={650} fill="var(--text)">{v === null ? "—" : v.toFixed(0)}</text>
      </svg>
      <figcaption>{title}</figcaption>
    </figure>
  );
}

/** The focus name's valuation percentile in four frames, its multiples and its re-rating direction. */
export function FourGauges({ result }: ViewProps) {
  const c = first(result, "four_dimension_valuation_card");
  if (!c?.ticker) return <Empty />;
  const abs = (c.absolute_valuation ?? {}) as Record<string, number | null>;
  const slope = (c.re_rating_slope ?? {}) as { interpretation?: string };
  return (
    <div className="vc">
      <div className="vc-head">
        <button type="button" className="tk-link vc-tk" onClick={() => openQuickLook(String(c.ticker))}>{String(c.ticker)}</button>
        <span className="vc-sec">{String(c.sector ?? "")}</span>
        {slope.interpretation ? <span className={`vc-trend ${slope.interpretation === "de-rating" ? "down" : "up"}`}>{label(slope.interpretation)}</span> : null}
      </div>
      <div className="vc-gauges">{DIMS.map(([k, t]) => <Gauge key={k} value={c[k]} title={t} />)}</div>
      <dl className="vc-mult">{Object.entries(abs).map(([k, v]) => <div key={k}><dt>{label(k)}</dt><dd className="num">{isNum(v) ? fmtKey(k, v) : "—"}</dd></div>)}</dl>
    </div>
  );
}

/** Every name as a small card with its four percentiles; sortable. */
export function ValuationCards({ rows }: ViewProps) {
  const [by, setBy] = useState("universe_percentile");
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a: Row, b: Row) => (isNum(a[by]) ? a[by] : 999) - (isNum(b[by]) ? b[by] : 999));
  return (
    <div className="vcards">
      <label className="vcards-sort">Sort by <select value={by} onChange={(e) => setBy(e.target.value)}>{DIMS.filter(([k]) => k in rows[0]).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
      <div className="vcards-grid">
        {sorted.map((r) => (
          <button type="button" key={String(r.ticker)} className="vcard" onClick={() => openQuickLook(String(r.ticker))}>
            <b>{String(r.ticker)}</b><span className="vcard-sec">{String(r.sector ?? "")}</span>
            {DIMS.filter(([k]) => k in r).map(([k, t]) => <span key={k} className="vcard-row"><span>{t.replace("vs ", "")}</span><i><u style={{ width: `${isNum(r[k]) ? r[k] : 0}%` }} /></i><em className="num">{isNum(r[k]) ? r[k].toFixed(0) : "—"}</em></span>)}
          </button>
        ))}
      </div>
    </div>
  );
}
