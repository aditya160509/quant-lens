/** Chart export: SVG and PNG with theme variables resolved, CSV from rows. */

const VAR_RE = /var\((--[\w-]+)\)/g;

function resolveVars(value: string, styles: CSSStyleDeclaration): string {
  return value.replace(VAR_RE, (_, name: string) => styles.getPropertyValue(name).trim() || "currentColor");
}

/** Serialize an on-screen SVG into a standalone file that renders without our stylesheet. */
export function serializeSvg(svg: SVGSVGElement): string {
  const styles = getComputedStyle(svg);
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const bg = styles.getPropertyValue("--panel").trim();
  const mono = styles.getPropertyValue("--font-jetbrains").trim() || "JetBrains Mono";
  const sans = styles.getPropertyValue("--font-inter").trim() || "Inter";
  clone.querySelectorAll<SVGElement>("*").forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      if (attr.value.includes("var(")) el.setAttribute(attr.name, resolveVars(attr.value, styles));
    }
    const inline = el.getAttribute("style");
    if (inline?.includes("var(")) el.setAttribute("style", resolveVars(inline, styles).replace(/var\(--mono\)/g, mono));
  });
  const rootStyle = (clone.getAttribute("style") ?? "").replace(/var\(--mono\)/g, `${mono}, monospace`).replace(/var\(--font\)/g, `${sans}, sans-serif`);
  clone.setAttribute("style", `${rootStyle};background:${bg}`);
  const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  rect.setAttribute("width", "100%");
  rect.setAttribute("height", "100%");
  rect.setAttribute("fill", bg);
  clone.insertBefore(rect, clone.firstChild);
  return new XMLSerializer().serializeToString(clone);
}

function download(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadSvg(svg: SVGSVGElement, name: string) {
  download(`${name}.svg`, new Blob([serializeSvg(svg)], { type: "image/svg+xml" }));
}

export async function downloadPng(svg: SVGSVGElement, name: string, scale = 3) {
  const src = serializeSvg(svg);
  const { width, height } = svg.viewBox.baseVal;
  const img = new Image();
  img.decoding = "async";
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(src)}`;
  await img.decode();
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0, width, height);
  canvas.toBlob((blob) => blob && download(`${name}.png`, blob), "image/png");
}

const csvCell = (v: unknown) => {
  if (v === null || v === undefined) return "";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
};

export function downloadCsv(rows: Record<string, unknown>[], name: string) {
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const text = [cols.join(","), ...rows.map((r) => cols.map((c) => csvCell(r[c])).join(","))].join("\n");
  download(`${name}.csv`, new Blob([text], { type: "text/csv" }));
}

export function downloadText(text: string, name: string, type = "text/plain") {
  download(name, new Blob([text], { type }));
}

export function downloadBase64(base64: string, name: string, type: string) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  download(name, new Blob([bytes], { type }));
}
