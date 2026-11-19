/** Blocks ⇄ formula. A rule is rows of `left op right`, joined by and/or. Only formulas of that shape convert back to blocks. */

export type Row = { left: string; op: string; right: string; join: "&" | "|" };
export const OPS: [string, string][] = [[">", "is above"], ["<", "is below"], [">=", "is at least"], ["<=", "is at most"], ["==", "equals"], ["crosses_above", "crosses above"], ["crosses_below", "crosses below"]];
const CROSS = new Set(["crosses_above", "crosses_below"]);

export function toFormula(rows: Row[]): string {
  return rows.filter((r) => r.left.trim() && r.right.trim())
    .map((r, i) => `${i ? ` ${r.join} ` : ""}${CROSS.has(r.op) ? `${r.op}(${r.left.trim()}, ${r.right.trim()})` : `(${r.left.trim()} ${r.op} ${r.right.trim()})`}`).join("");
}

/** Split on top-level & and | (outside brackets). */
function splitTop(s: string): { parts: string[]; joins: ("&" | "|")[] } {
  const parts: string[] = [], joins: ("&" | "|")[] = [];
  let depth = 0, cur = "";
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (depth === 0 && (ch === "&" || ch === "|")) { parts.push(cur); joins.push(ch); cur = ""; } else cur += ch;
  }
  parts.push(cur);
  return { parts: parts.map((p) => p.trim()), joins };
}

const unwrap = (s: string): string => {
  s = s.trim();
  if (!s.startsWith("(") || !s.endsWith(")")) return s;
  let depth = 0;
  for (let i = 0; i < s.length; i++) { if (s[i] === "(") depth++; if (s[i] === ")") depth--; if (depth === 0 && i < s.length - 1) return s; }
  return unwrap(s.slice(1, -1));
};

/** Formula → rows, or null when the formula is not a flat and/or of comparisons. */
export function fromFormula(text: string): Row[] | null {
  if (!text.trim()) return [];
  const { parts, joins } = splitTop(unwrap(text));
  const rows: Row[] = [];
  for (const [i, raw] of parts.entries()) {
    const p = unwrap(raw), join = i ? joins[i - 1] : "&";
    const cross = /^(crosses_above|crosses_below)\((.*)\)$/.exec(p);
    if (cross) {
      let depth = 0, at = -1;
      for (let k = 0; k < cross[2].length; k++) { const c = cross[2][k]; if (c === "(") depth++; if (c === ")") depth--; if (c === "," && depth === 0) { at = k; break; } }
      if (at < 0) return null;
      rows.push({ left: cross[2].slice(0, at).trim(), op: cross[1], right: cross[2].slice(at + 1).trim(), join });
      continue;
    }
    let depth = 0, hit: { at: number; op: string } | null = null;
    for (let k = 0; k < p.length; k++) {
      const c = p[k];
      if (c === "(") depth++;
      if (c === ")") depth--;
      if (depth) continue;
      const two = p.slice(k, k + 2);
      if ([">=", "<=", "=="].includes(two)) { if (hit) return null; hit = { at: k, op: two }; k++; }
      else if (c === ">" || c === "<") { if (hit) return null; hit = { at: k, op: c }; }
    }
    if (!hit) return null;
    rows.push({ left: p.slice(0, hit.at).trim(), op: hit.op, right: p.slice(hit.at + hit.op.length).trim(), join });
  }
  return rows;
}

/** The server's Any/All tree (spec.groups[role]): a condition is a formula string or {rule, enabled}; a group nests to 10 deep. */
export type Leaf = { rule: string; enabled?: boolean };
export type Group = { op: "all" | "any"; items: Item[] };
export type Item = Leaf | Group | string;

/** Field-by-field changes between two specs, flattened to dotted keys. */
export function specDiff(a: Record<string, unknown>, b: Record<string, unknown>): [string, string, string][] {
  const flat = (o: unknown, pre = ""): Record<string, string> => (o && typeof o === "object" && !Array.isArray(o)
    ? Object.assign({}, ...Object.entries(o).map(([k, v]) => flat(v, pre ? `${pre}.${k}` : k))) : { [pre]: o === null || o === undefined ? "" : typeof o === "object" ? JSON.stringify(o) : String(o) });
  const fa = flat(a), fb = flat(b);
  return [...new Set([...Object.keys(fa), ...Object.keys(fb)])].filter((k) => k !== "blocks" && (fa[k] ?? "") !== (fb[k] ?? "")).map((k) => [k, fa[k] ?? "", fb[k] ?? ""]);
}
