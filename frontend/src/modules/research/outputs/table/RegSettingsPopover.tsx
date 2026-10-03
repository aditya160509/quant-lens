"use client";

import * as Popover from "@radix-ui/react-popover";
import { ArrowDown, ArrowUp, Settings2 } from "lucide-react";
import type { Row } from "../../types";
import { allGofKeys, allTermKeys, buildModel } from "./regression";
import { DEFAULT_REG, useRegSettings, useTableSettings, type StatUnder } from "./settings";

export function RegSettingsPopover({ scope, rows }: { scope: string; rows: Row[] }) {
  const s = useRegSettings(scope);
  const patch = useTableSettings((x) => x.patch);
  const reset = useTableSettings((x) => x.reset);
  const set = (p: Partial<typeof s>) => patch(scope, p);
  const keys = buildModel(rows, { ...DEFAULT_REG, order: s.order }).terms.map((t) => t.key);
  const all = allTermKeys(rows);
  const gofAll = allGofKeys(rows);
  const move = (k: string, d: number) => {
    const o = [...keys]; const i = o.indexOf(k); const j = i + d;
    if (j < 0 || j >= o.length) return;
    [o[i], o[j]] = [o[j], o[i]];
    set({ order: o });
  };
  return (
    <Popover.Root>
      <Popover.Trigger asChild><button className="btn sm ghost" aria-label="Table settings"><Settings2 size={13} />Table settings</button></Popover.Trigger>
      <Popover.Portal container={typeof document === "undefined" ? undefined : document.querySelector<HTMLElement>(".ws")}>
        <Popover.Content className="tbl-pop" align="end" sideOffset={6} collisionPadding={12}>
          <label className="tp-row"><span>Statistic under estimate</span>
            <select value={s.stat} onChange={(e) => set({ stat: e.target.value as StatUnder })}>
              <option value="se">Standard error</option><option value="t">t-statistic</option><option value="ci">95% CI</option><option value="p">p-value</option><option value="none">None</option>
            </select></label>
          <label className="tp-row"><span>Layout</span>
            <select value={s.layout} onChange={(e) => set({ layout: e.target.value as "stacked" | "side" })}>
              <option value="side">Side by side</option><option value="stacked">Stacked</option>
            </select></label>
          <label className="tp-row"><span>Significance stars</span><input type="checkbox" checked={s.stars} onChange={(e) => set({ stars: e.target.checked })} /></label>
          {s.stars ? (
            <div className="tp-row"><span>Thresholds</span>
              <span className="tp-th">{s.thresholds.map((v, i) => (
                <input key={i} type="number" step="0.01" min="0" max="1" value={v} aria-label={`${"*".repeat(i + 1)} threshold`}
                  onChange={(e) => { const t = [...s.thresholds] as [number, number, number]; t[i] = Number(e.target.value); set({ thresholds: t }); }} />
              ))}</span></div>
          ) : null}
          <label className="tp-col"><span>Title</span><input type="text" value={s.title} onChange={(e) => set({ title: e.target.value })} /></label>
          <label className="tp-col"><span>Notes</span><input type="text" value={s.notes} onChange={(e) => set({ notes: e.target.value })} /></label>
          <div className="tp-h">Terms: rename, omit, reorder</div>
          <div className="tp-list">
            {[...keys, ...all.filter((k) => !keys.includes(k))].map((k) => {
              const off = s.omit.includes(k);
              return (
                <div key={k} className="tp-term">
                  <input type="checkbox" checked={!off} aria-label={`Show ${k}`} onChange={() => set({ omit: off ? s.omit.filter((x) => x !== k) : [...s.omit, k] })} />
                  <input type="text" placeholder={k} value={s.rename[k] ?? ""} onChange={(e) => set({ rename: { ...s.rename, [k]: e.target.value } })} />
                  <button className="btn sm ghost" aria-label="Move up" onClick={() => move(k, -1)}><ArrowUp size={11} /></button>
                  <button className="btn sm ghost" aria-label="Move down" onClick={() => move(k, 1)}><ArrowDown size={11} /></button>
                </div>
              );
            })}
          </div>
          {gofAll.length ? (
            <>
              <div className="tp-h">Goodness-of-fit rows</div>
              <div className="tp-gof">
                {gofAll.map((k) => {
                  const on = !s.gof || s.gof.includes(k);
                  return (
                    <label key={k}><input type="checkbox" checked={on} onChange={() => { const cur = s.gof ?? gofAll; set({ gof: on ? cur.filter((x) => x !== k) : [...cur, k] }); }} />{k.replace(/_/g, " ")}</label>
                  );
                })}
              </div>
            </>
          ) : null}
          <button className="btn sm" onClick={() => reset(scope)}>Reset to defaults</button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
