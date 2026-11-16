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
