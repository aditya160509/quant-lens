export const T = {
  page: "#080907", panel: "#0e100d", raised: "#151812", screen: "#070806",
  border: "#2a2d25", subtle: "#1c1f1a", grid: "#252820", amber: "#e6ad36",
  amberSoft: "rgba(230,173,54,.12)", text: "#f1efe7", secondary: "#aaa99f", muted: "#706f66",
  green: "#67b67b", red: "#e26e5c", blue: "#70a5d7", violet: "#a68ad2",
};
export const SERIES = [T.amber, T.blue, T.green, T.violet, T.red, T.secondary];
export const axis = { tick: { fill: T.muted, fontSize: 10, fontFamily: "var(--font-ibm-plex-mono), monospace" }, axisLine: false, tickLine: false };
export const tooltipStyle = { background: T.raised, border: `1px solid ${T.border}`, borderRadius: 7, color: T.text, fontSize: 11 };

export const isNum = (v) => typeof v === "number" && Number.isFinite(v);

export function fmt(v, digits = 4) {
  if (v === null || v === undefined) return "–";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "–";
  if (typeof v === "object") return JSON.stringify(v);
  if (!isNum(v)) return String(v);
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-4 || a >= 1e6)) return v.toExponential(2);
  if (Number.isInteger(v)) return v.toLocaleString();
  return v.toFixed(a >= 100 ? 1 : digits);
}

export const title = (s) => String(s ?? "").replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function pColor(p) {
  if (!isNum(p)) return T.muted;
  return p < 0.01 ? T.green : p < 0.05 ? T.amber : T.muted;
}

export function downloadText(filename, text, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadBase64(filename, base64, type) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
