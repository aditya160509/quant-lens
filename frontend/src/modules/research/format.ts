import type { FeatureResult, Row } from "./types";

export const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

const ACRONYMS: Record<string, string> = {
  ols: "OLS", nw: "NW", fm: "FM", grs: "GRS", gmm: "GMM", gls: "GLS", iv: "IV", did: "DiD", rd: "RD", rdd: "RD", bhar: "BHAR", liml: "LIML", "2sls": "2SLS", psr: "PSR", car: "CAR", att: "ATT", ls: "L/S",
  oos: "OOS", is: "IS", se: "SE", r2: "R²", vif: "VIF", ic: "IC", ir: "IR", hlz: "HLZ", rmspe: "RMSPE", scm: "SCM", qq: "Q-Q",
  ar: "AR", tsls: "2SLS", vix: "VIX", cs: "CS", pdf: "PDF", csv: "CSV", bm: "B/M", ivol: "IVOL", us: "US", ff5: "FF5", bhy: "BHY",
  mr: "MR", hhi: "HHI", aic: "AIC", bic: "BIC", smd: "SMD", twfe: "TWFE", fe: "FE", mkt: "Mkt", rf: "RF", smb: "SMB", hml: "HML",
  rmw: "RMW", cma: "CMA", dfbeta: "DFBETA", dffits: "DFFITS", ci90: "90% CI", ci: "CI", pct: "%", "5pct": "5%", "10pct": "10%",
  vs: "vs", t: "t", p: "p", auto: "auto", n: "N", jb: "JB", ff3: "FF3", mom: "Momentum", hl: "HL", ex: "ex", id: "ID",
};

/** snake_case to a readable label: "standard_errors" → "Standard errors", "nw_auto" → "NW auto". */
export function label(key: unknown): string {
  const words = String(key ?? "").replace(/[-_]+/g, " ").trim().split(/\s+/);
  return words
    .map((w, i) => {
      // Tickers arrive upper case ("GE", "T"); keys arrive lower case. Never title-case a ticker.
      if (/^[A-Z][A-Z0-9.]*$/.test(w)) return w;
      const k = w.toLowerCase();
      if (ACRONYMS[k]) return ACRONYMS[k];
      return i === 0 ? k.charAt(0).toUpperCase() + k.slice(1) : k;
    })
    .join(" ")
    .replace(/(\d) (?=\d)/g, "$1-"); // "mom 12 1" reads "Momentum 12-1"
}

/** Number formatting tuned for statistics: fixed decimals, exponent only when needed. */
export function num(v: unknown, digits = 3): string {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (!isNum(v)) return String(v);
  const a = Math.abs(v);
  if (a === 0) return "0";
  if (a >= 1e7 || a < 10 ** -(digits + 1)) return v.toExponential(2).replace("e+", "e");
  if (Number.isInteger(v) && a >= 1) return v.toLocaleString("en-US");
  if (a >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 1 });
  return v.toFixed(digits);
}

export const pct = (v: unknown, digits = 1) => (isNum(v) ? `${(v * 100).toFixed(digits)}%` : "–");
export const pval = (v: unknown) => (isNum(v) ? (v < 0.0001 ? "<0.0001" : v.toFixed(4)) : "–");
export const tstat = (v: unknown) => (isNum(v) ? v.toFixed(2) : "–");

export function pTone(p: unknown): "up" | "warn" | "neutral" {
  if (!isNum(p)) return "neutral";
  return p < 0.01 ? "up" : p < 0.05 ? "warn" : "neutral";
}

export const toneVar = (t: string | null | undefined) =>
  t === "up" ? "var(--up)" : t === "warn" ? "var(--warn)" : t === "down" ? "var(--down)" : t === "accent" ? "var(--accent)" : undefined;

export function stars(p: unknown): string {
  if (!isNum(p)) return "";
  return p < 0.01 ? "***" : p < 0.05 ? "**" : p < 0.1 ? "*" : "";
}

export function rowsOf(v: unknown): Row[] {
  if (Array.isArray(v)) return v.filter((r): r is Row => Boolean(r) && typeof r === "object");
  if (v && typeof v === "object") return [v as Row];
  return [];
}

export function columns(rows: Row[]): string[] {
  return [...new Set(rows.flatMap((r) => Object.keys(r)))];
}

/** Value of an output from the tables, charts or sections block of a result. */
export function out(result: FeatureResult, key: string): Row[] {
  return rowsOf(result.tables?.[key] ?? result.charts?.[key] ?? result.sections?.[key]);
}

export const first = (result: FeatureResult, key: string): Row | undefined => out(result, key)[0];

const P_RE = /(^|_)(p|pvalue|p_value)$|p_value|^pr\(/i;
const T_RE = /(^|_)t(_stat)?$|_t$|^t_|t_stat|z$|^stouffer_z$/i;
const PCT_RE = /(return|spread|share|fraction|weight|coverage|power|survival|probability|drawdown|r2$|^r2|accuracy)/i;
const INT_RE = /(months|periods|nobs|observations|count|^n$|_n$|^n_|replications|tests|assets|units|cohorts|events|donors|lag|rank|placebos|specifications|choices|length|window|holdings|pairs$)/i;

export const isPKey = (k: string) => P_RE.test(k);
export const isTKey = (k: string) => !isPKey(k) && T_RE.test(k);

/** Format a value by what its column name says it is. */
export function fmtKey(key: string, v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.map((x) => (isNum(x) ? num(x) : label(x))).join(", ") : "–";
  if (v && typeof v === "object") return Object.entries(v).map(([k, x]) => `${label(k)} ${num(x)}`).join(" · ");
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "string") {
    if (/^\d{4}-\d{2}-\d{2}/.test(v)) return v.slice(0, 10);
    if (/^[a-z0-9]+(_[a-z0-9]+)+$/.test(v)) return label(v);
    return v;
  }
  if (!isNum(v)) return "–";
  if (isPKey(key)) return pval(v);
  if (isTKey(key)) return tstat(v);
  if (INT_RE.test(key) && Number.isInteger(v)) return v.toLocaleString("en-US");
  if (PCT_RE.test(key) && Math.abs(v) <= 5) return pct(v, Math.abs(v) < 0.01 ? 2 : 1);
  return num(v, Math.abs(v) < 0.1 ? 4 : 3);
}

/** Back-compat alias used by table cells. */
export const cell = (v: unknown, key = "") => fmtKey(key, v);

/** Readable value of one analyst choice in a specification. */
export function choiceLabel(dim: string, v: string): string {
  if (dim === "controls") return v === "base" ? "Study controls" : v === "none" || v === "" ? "None" : v.split(",").map((c) => label(c)).join(" + ");
  return label(v);
}

/** "subsample=pre_2020; universe=large_cap" → "Subsample: Pre 2020 · Universe: Large cap". */
export function specTitle(spec: unknown): string {
  const s = String(spec ?? "");
  if (s === "base") return "Base specification";
  return s.split(";").map((part) => {
    const [dim, value = ""] = part.trim().split("=");
    return `${label(dim)}: ${choiceLabel(dim, value)}`;
  }).join(" · ");
}

/** Signed significance tone for an estimate with a p-value. */
export function sigTone(estimate: unknown, p: unknown): "up" | "down" | null {
  if (!isNum(estimate) || !isNum(p) || p >= 0.05) return null;
  return estimate > 0 ? "up" : "down";
}
