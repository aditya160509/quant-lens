"use client";

import { useMemo, useState } from "react";
import { diverging, parseDate, Svg, useWidth } from "./core";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** Missing months remain explicitly missing; duplicate observations are averaged or summed as requested. */
export function CalendarHeatmap({ data, title, signed = true, aggregate = "mean", hourly = false, format = (v: number) => v.toFixed(3) }: {
  data: { date: string | number; value: number }[]; title: string; signed?: boolean; aggregate?: "mean" | "sum"; hourly?: boolean; format?: (v: number) => string;
}) {
  const [hourView, setHourView] = useState(false);
  const byHour = hourly && hourView;
  const headings = byHour ? Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}`) : MONTHS;
  const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const [ref, width] = useWidth<HTMLDivElement>();
  const cells = useMemo(() => {
    const groups = new Map<string, { sum: number; count: number }>();
    data.forEach((d) => { const t = parseDate(d.date); if (t === null || !Number.isFinite(d.value)) return; const date = new Date(t), key = byHour ? `${(date.getUTCDay() + 6) % 7}-${date.getUTCHours()}` : `${date.getUTCFullYear()}-${date.getUTCMonth()}`; const group = groups.get(key) ?? { sum: 0, count: 0 }; group.sum += d.value; group.count++; groups.set(key, group); });
    return new Map([...groups].map(([key, v]) => [key, v.sum / (aggregate === "mean" ? v.count : 1)]));
  }, [data, aggregate, byHour]);
  const years = byHour && cells.size ? Array.from({ length: 7 }, (_, i) => i) : [...new Set([...cells.keys()].map((k) => Number(k.split("-")[0])))].sort((a, b) => a - b);
  const rowName = (year: number) => byHour ? weekdays[year] : String(year);
  const cellName = (year: number, i: number) => byHour ? `${weekdays[year]} ${headings[i]}:00 UTC` : `${headings[i]} ${year}`;
  const max = Math.max(...[...cells.values()].map(Math.abs), 1e-12);
  if (!years.length) return <div ref={ref}><p className="chart-empty">No dated observations to display.</p></div>;
  const chartWidth = Math.max(byHour ? 980 : 620, width);
  const cellWidth = (chartWidth - 50) / headings.length;
  const fill = (v: number | undefined) => v === undefined ? "var(--panel-2)" : signed ? diverging(v / max) : `color-mix(in oklch, var(--accent) ${Math.round(Math.max(0, v) / max * 65)}%, var(--panel))`;
  return <div ref={ref} className="calendar-chart">
    {hourly ? <div className="chart-mode-tabs" role="group" aria-label="Activity calendar"><button aria-pressed={!byHour} onClick={() => setHourView(false)}>By month</button><button aria-pressed={byHour} onClick={() => setHourView(true)}>Weekday × hour (UTC)</button></div> : null}
    <div className="calendar-scroll" tabIndex={0} role="region" aria-label={title}>
      <Svg width={chartWidth} height={years.length * 40 + 30} label={`${title}. ${byHour ? "Weekday by hour, UTC" : `${years.length} years, monthly ${aggregate}`}. Missing observations marked with a dash.`}>
        {headings.map((m, i) => <text key={m} x={50 + (i + 0.5) * cellWidth} y={17} textAnchor="middle" fontSize={11} fill="var(--text-2)">{m}</text>)}
        {years.map((year, yi) => <g key={year}>
          <text x={2} y={54 + yi * 40} fontSize={11} fill="var(--text-2)">{rowName(year)}</text>
          {headings.map((month, mi) => { const v = cells.get(`${year}-${mi}`); const x = 50 + mi * cellWidth, y = 30 + yi * 40; return <g key={month}>
            <title>{cellName(year, mi)}: {v === undefined ? "No observation" : format(v)}</title>
            <rect x={x + 2} y={y} width={cellWidth - 4} height={36} fill={fill(v)} />
            <text x={x + cellWidth / 2} y={y + 22} textAnchor="middle" fontSize={10.5} fill="var(--text)" stroke="var(--panel)" strokeWidth={3} paintOrder="stroke">{v === undefined ? "–" : format(v)}</text>
          </g>; })}
        </g>)}
      </Svg>
      <table className="calendar-table calendar-data"><caption>{title}</caption><thead><tr><th scope="col">{byHour ? "UTC" : "Year"}</th>{headings.map((m) => <th key={m} scope="col">{m}</th>)}</tr></thead>
        <tbody>{years.map((year) => <tr key={year}><th scope="row">{rowName(year)}</th>{headings.map((m, i) => { const v = cells.get(`${year}-${i}`); return <td key={m} title={`${cellName(year, i)}: ${v === undefined ? "No observation" : format(v)}`} ><span>{v === undefined ? "–" : format(v)}</span></td>; })}</tr>)}</tbody>
      </table>
    </div>
    <p className="calendar-note">{signed ? "Negative" : "Fewer"}<span className="calendar-ramp" aria-hidden>{[0, 1, 2, 3, 4].map((i) => <i key={i} style={{ background: signed ? diverging((i - 2) / 2) : `color-mix(in oklch, var(--accent) ${i * 16}%, var(--panel))` }} />)}</span>{signed ? "Positive" : "More"}<span>– No observation · {aggregate === "mean" ? byHour ? "Hourly mean" : "Monthly mean" : byHour ? "Hourly total" : "Monthly total"}</span></p>
  </div>;
}
