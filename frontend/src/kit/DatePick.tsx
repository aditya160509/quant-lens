"use client";

import * as Popover from "@radix-ui/react-popover";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const shown = (s: string) => parse(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const WEEK = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

/** A date field: a button that opens a month calendar with quick picks. Empty means the latest data. */
export function DatePick({ value, onChange, min, max, label, empty = "Latest" }: { value: string; onChange: (v: string) => void; min?: string; max?: string; label: string; empty?: string }) {
  const [open, setOpen] = useState(false);
  const base = value ? parse(value) : max ? parse(max) : new Date();
  const [month, setMonth] = useState(new Date(base.getFullYear(), base.getMonth(), 1));
  const ok = (s: string) => (!min || s >= min) && (!max || s <= max);
  const pick = (s: string) => { onChange(s); setOpen(false); };
  const end = max ? parse(max) : new Date();
  const back = (days: number) => iso(new Date(end.getFullYear(), end.getMonth(), end.getDate() - days));
  const quick: [string, string][] = [["1M ago", back(30)], ["3M ago", back(91)], ["1Y ago", back(365)], ["3Y ago", back(1095)]];
  const lead = (month.getDay() + 6) % 7;
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells = [...Array(lead).fill(null), ...Array.from({ length: days }, (_, i) => iso(new Date(month.getFullYear(), month.getMonth(), i + 1)))];
  const shift = (n: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1));
  return (
    <Popover.Root open={open} onOpenChange={(o) => { setOpen(o); if (o) setMonth(new Date(base.getFullYear(), base.getMonth(), 1)); }}>
      <Popover.Trigger asChild>
        <button type="button" className="dp-btn" aria-label={label} data-set={!!value}><CalendarDays size={14} aria-hidden />{value ? shown(value) : empty}</button>
      </Popover.Trigger>
      <Popover.Portal container={typeof document === "undefined" ? undefined : document.querySelector<HTMLElement>(".ws")}>
        <Popover.Content className="dp-pop" align="start" sideOffset={6} collisionPadding={12}>
          <div className="dp-quick">
            <button type="button" aria-pressed={!value} onClick={() => pick("")}>{empty}</button>
            {quick.filter(([, s]) => ok(s)).map(([t, s]) => <button key={t} type="button" aria-pressed={value === s} onClick={() => pick(s)}>{t}</button>)}
          </div>
          <div className="dp-head">
            <button type="button" aria-label="Previous month" onClick={() => shift(-1)}><ChevronLeft size={15} /></button>
            <span>{month.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</span>
            <button type="button" aria-label="Next month" onClick={() => shift(1)}><ChevronRight size={15} /></button>
          </div>
          <div className="dp-grid" role="grid">
            {WEEK.map((w) => <span key={w} className="dp-w">{w}</span>)}
            {cells.map((s, i) => s === null ? <span key={`b${i}`} /> : (
              <button key={s} type="button" disabled={!ok(s)} aria-pressed={value === s} data-today={s === iso(new Date())} onClick={() => pick(s)}>{parse(s).getDate()}</button>
            ))}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
