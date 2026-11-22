/** Pure keymap helpers: canonical combos, chords ("Cmd+K Cmd+S"), conflicts. */
const MOD: Record<string, string> = { cmd: "cmd", ctrl: "cmd", meta: "cmd", "⌘": "cmd", shift: "shift", "⇧": "shift", alt: "alt", option: "alt", opt: "alt", "⌥": "alt" };

/** "Ctrl+K" -> "cmd+k"; modifiers ordered cmd, shift, alt. */
export function normCombo(text: string): string {
  const mods = new Set<string>(); let key = "";
  for (const raw of text.split("+").map((x) => x.trim().toLowerCase()).filter(Boolean)) { if (MOD[raw]) mods.add(MOD[raw]); else key = raw === "return" ? "enter" : raw; }
  return [...["cmd", "shift", "alt"].filter((m) => mods.has(m)), key].filter(Boolean).join("+");
}
/** "Cmd+K  Cmd+S" -> ["cmd+k", "cmd+s"]. */
export const normChord = (text: string): string[] => text.trim().split(/\s+/).filter(Boolean).map(normCombo);

export function comboFromEvent(e: { metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean; key: string; code?: string }): string {
  const k = e.code?.startsWith("Key") ? e.code.slice(3) : e.code?.startsWith("Digit") ? e.code.slice(5) : e.key;
  return normCombo([e.metaKey || e.ctrlKey ? "cmd" : "", e.shiftKey ? "shift" : "", e.altKey ? "alt" : "", k].filter(Boolean).join("+"));
}

/** Contexts a binding can require: "F5 when !debugPaused", "Cmd+E when cellsFile && !testFile". */
export const WHEN = ["debugPaused", "panelOpen", "cellsFile", "testFile"] as const;
/** "Cmd+K when debugPaused" -> { keys: "Cmd+K", when: "debugPaused" }. */
export const splitWhen = (text: string): { keys: string; when: string } => { const [keys = "", when = ""] = text.split(/\s+when\s+/i); return { keys: keys.trim(), when: when.trim() }; };
/** A when clause as a Monaco context expression ("studio.x && !studio.y"), or null when it names an unknown context. */
export function whenExpr(when: string): string | null {
  if (!when) return null;
  const terms = when.split(/\s*&&\s*/);
  const ok = terms.every((t) => (WHEN as readonly string[]).includes(t.replace(/^!/, "")));
  return ok ? terms.map((t) => (t.startsWith("!") ? `!studio.${t.slice(1)}` : `studio.${t}`)).join(" && ") : null;
}

export const FIXED: [string, string, string][] = [["studio.save", "Save", "Cmd+S"], ["studio.run", "Run", "Cmd+Enter"], ["studio.formatSelection", "Format selection", "Cmd+K Cmd+F"], ["studio.organiseImports", "Organise imports", "Shift+Alt+O"]];

/** Id of the action that already uses `text` (same chord, or one is a prefix of the other), else null. */
export function conflictWith(id: string, text: string, user: Record<string, string>, fixed = FIXED): string | null {
  const mine = splitWhen(text), a = normChord(mine.keys); if (!a.length) return null;
  const all: [string, string][] = [...fixed.map(([i, , k]) => [i, k] as [string, string]), ...Object.entries(user).filter(([i]) => !fixed.some((f) => f[0] === i))];
  for (const [other, keys] of all) {
    if (other === id) continue;
    const theirs = splitWhen(keys);
    if (mine.when && theirs.when && mine.when !== theirs.when) continue; // different contexts never fire together
    const b = normChord(theirs.keys); const n = Math.min(a.length, b.length);
    if (n && a.slice(0, n).join(" ") === b.slice(0, n).join(" ")) return other;
  }
  return null;
}

/** First steps of all two-step chords, to know when to show the waiting hint. */
export const chordStarts = (user: Record<string, string>, fixed = FIXED): Set<string> =>
  new Set([...fixed.map((f) => f[2]), ...Object.values(user).map((k) => splitWhen(k).keys)].map(normChord).filter((c) => c.length > 1).map((c) => c[0]));
