"use client";

import { Empty } from "@/kit/DataTable";
import { useStudies } from "@/modules/research/store";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./formula.css";

/** Ready-made formulas as cards; Use puts the expression into the formula box. */
export function TemplateGallery({ rows }: ViewProps) {
  const current = useStudies((s) => String(s.forms.sc02?.formula ?? ""));
  if (!rows.length) return <Empty />;
  const use = (expression: string) => useStudies.setState((s) => ({ forms: { ...s.forms, sc02: { ...s.forms.sc02, formula: expression } } }));
  return (
    <div className="fg">
      {rows.map((r) => {
        const expr = String(r.expression ?? "");
        const on = expr === current;
        return (
          <article key={String(r.name)} className="fg-card" data-on={on}>
            <h4>{String(r.name)}</h4>
            <code>{expr}</code>
            <button type="button" className={`btn sm${on ? "" : " primary"}`} disabled={on} onClick={() => use(expr)}>{on ? "In use" : "Use"}</button>
          </article>
        );
      })}
    </div>
  );
}

/** Parser and evaluation status, one line each, worst first. */
export function FormulaStatus({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const order: Record<string, number> = { error: 0, warn: 1, warning: 1, ok: 2 };
  return (
    <ul className="fstat">
      {[...rows].sort((a, b) => (order[String(a.level)] ?? 3) - (order[String(b.level)] ?? 3)).map((r, i) => (
        <li key={i} data-level={String(r.level)}><span>{String(r.level ?? "").toUpperCase()}</span>{String(r.message ?? "")}</li>
      ))}
    </ul>
  );
}
