import { isNum, label, num, pval } from "../../format";
import type { Row } from "../../types";
import { DEFAULT_REG, type RegSettings } from "./settings";

export type Term = { key: string; name: string; est: number | null; se: number | null; t: number | null; p: number | null; lo: number | null; hi: number | null };
export type Model = { labelKey: string; terms: Term[]; gof: { k: string; name: string; v: unknown }[]; extra: string[] };

const pick = (r: Row, ks: string[]) => ks.find((k) => k in r);
const nn = (v: unknown) => (isNum(v) ? v : null);

export function buildModel(rows: Row[], s: RegSettings): Model {
  const r0 = rows[0];
  const lab = pick(r0, ["term", "regime", "estimator", "factor", "quantile"]) ?? Object.keys(r0)[0];
  const coef = pick(r0, ["lambda", "coefficient", "estimate", "iv_coefficient", "slope_on_condition"]);
  const se = pick(r0, ["nw_se", "se", "iv_se", "se_robust"]);
  const t = pick(r0, ["t_stat", "iv_t"]);
  const p = pick(r0, ["p_value", "iv_p", "p_value_robust"]);
  const used = new Set([lab, coef, se, t, p, "stars", "lower_95", "upper_95"]);
  const extra = Object.keys(r0).filter((k) => !used.has(k) && !rows.every((r) => r[k] === r0[k])).slice(0, 3);
  const sharedKeys = Object.keys(r0).filter((k) => !used.has(k) && !extra.includes(k) && rows.every((r) => r[k] === r0[k]));
  let terms: Term[] = rows.map((r) => {
    const key = String(r[lab] ?? "");
    const est = coef ? nn(r[coef]) : null, sev = se ? nn(r[se]) : null;
    return { key, name: s.rename[key] || key, est, se: sev, t: t ? nn(r[t]) : est !== null && sev ? est / sev : null, p: p ? nn(r[p]) : null,
      lo: nn(r.lower_95) ?? (est !== null && sev !== null ? est - 1.96 * sev : null), hi: nn(r.upper_95) ?? (est !== null && sev !== null ? est + 1.96 * sev : null) };
  }).filter((x) => !s.omit.includes(x.key));
  if (s.order.length) {
    const ix = (k: string) => { const i = s.order.indexOf(k); return i < 0 ? 1e9 : i; };
    terms = [...terms].sort((a, b) => ix(a.key) - ix(b.key));
  }
  const gof = sharedKeys.filter((k) => !s.gof || s.gof.includes(k)).map((k) => ({ k, name: label(k), v: r0[k] }));
  return { labelKey: lab, terms, gof, extra };
}

export const allTermKeys = (rows: Row[]) => buildModel(rows, DEFAULT_REG).terms.map((x) => x.key);
export const allGofKeys = (rows: Row[]) => buildModel(rows, DEFAULT_REG).gof.map((g) => g.k);

export function starsFor(p: number | null, s: RegSettings): string {
  if (!s.stars || p === null) return "";
  const [a, b, c] = s.thresholds;
  return p < c ? "***" : p < b ? "**" : p < a ? "*" : "";
}

export function statText(x: Term, s: RegSettings): string {
  switch (s.stat) {
    case "se": return x.se === null ? "" : `(${num(x.se, 4)})`;
    case "t": return x.t === null ? "" : `(${x.t.toFixed(2)})`;
    case "p": return x.p === null ? "" : `(${pval(x.p)})`;
    case "ci": return x.lo === null || x.hi === null ? "" : `[${num(x.lo, 3)}, ${num(x.hi, 3)}]`;
    default: return "";
  }
}

export const STAT_NAME: Record<string, string> = { se: "Standard errors", t: "t-statistics", p: "p-values", ci: "95% confidence intervals", none: "" };

export function notesText(s: RegSettings): string {
  const bits = [s.stat !== "none" ? `${STAT_NAME[s.stat]} in ${s.stat === "ci" ? "brackets" : "parentheses"}.` : "", s.stars ? `${s.thresholds.map((v, i) => "*".repeat(i + 1) + " p<" + v).reverse().join(", ")}.` : "", s.notes];
  return bits.filter(Boolean).join(" ");
}

const esc = (v: string) => v.replace(/([&%$#_{}])/g, "\\$1");

export function regressionLatex(m: Model, s: RegSettings): string {
  const L: string[] = ["\\begin{table}[htbp]\\centering"];
  if (s.title) L.push(`\\caption{${esc(s.title)}}`);
  L.push("\\begin{tabular}{lc}", "\\hline\\hline", `${esc(label(m.labelKey))} & Estimate \\\\`, "\\hline");
  for (const x of m.terms) {
    L.push(`${esc(x.name)} & ${x.est === null ? "" : num(x.est, 4)}${starsFor(x.p, s) ? `$^{${starsFor(x.p, s)}}$` : ""} \\\\`);
    const st = statText(x, s);
    if (st) L.push(` & ${st.replace(/%/g, "\\%")} \\\\`);
  }
  if (m.gof.length) L.push("\\hline", ...m.gof.map((g) => `${esc(g.name)} & ${esc(String(g.v))} \\\\`));
  L.push("\\hline\\hline", "\\end{tabular}");
  const n = notesText(s);
  if (n) L.push(`\\par\\footnotesize ${esc(n).replace(/\*/g, "$^*$")}`);
  L.push("\\end{table}");
  return L.join("\n");
}
