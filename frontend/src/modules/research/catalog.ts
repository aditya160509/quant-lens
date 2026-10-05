import { ClipboardCheck, CloudLightning, Crosshair, FlaskConical, GitFork, Hourglass, Layers, PawPrint, ShieldCheck, Sigma, Stethoscope, Table2 } from "lucide-react";
import { lab, type FeatureMeta, type Page } from "./lab";

export type { Page } from "./lab";

/** How each Research feature is presented: a short name, an icon and the question it answers. Keyed by backend feature id. */
export const RESEARCH_CATALOG: Record<string, FeatureMeta> = {
  "01": { name: "Canonical tests", slug: "canonical", icon: Sigma, question: "Does the signal price the cross-section of returns?" },
  "02": { name: "Robustness", slug: "robustness", icon: GitFork, question: "Does the result survive every reasonable analysis choice?" },
  "03": { name: "Placebo suite", slug: "placebo", icon: ShieldCheck, question: "Would a fake version of the signal look just as good?" },
  "04": { name: "Regimes", slug: "regimes", icon: CloudLightning, question: "Does the premium change with market conditions?" },
  "05": { name: "Diagnostics", slug: "diagnostics", icon: Stethoscope, question: "Do the regressions meet their assumptions?" },
  "06": { name: "Publication table", slug: "publication", icon: Table2, question: "What does the journal-ready table look like?" },
  "07": { name: "Causal designs", slug: "causal", icon: Crosshair, question: "Is the effect causal under DiD, event-study, RD or IV designs?" },
  "08": { name: "Signal decay", slug: "decay", icon: Hourglass, question: "How fast is the signal being arbitraged away?" },
  "09": { name: "Synthetic control", slug: "synthetic", icon: Layers, question: "What would the treated unit have done without the event?" },
  "11": { name: "Factor zoo", slug: "factor-zoo", icon: PawPrint, question: "Is the signal new, or a known factor in disguise?" },
};

/**
 * The workspace's pages. Tests that answer one question share a page and are switched in its header,
 * so the nav shows six destinations instead of ten. Publication lives under Export on every page.
 */
export const RESEARCH_PAGES: Page[] = [
  { id: "signal", slug: "signal", label: "Signal", icon: FlaskConical, question: "Write, load or combine the signal you want to test.", features: [] },
  { id: "report", slug: "report", label: "Report card", icon: ClipboardCheck, question: "One verdict across every test, graded like a referee would.", features: [] },
  { id: "pricing", label: "Pricing tests", icon: Sigma, question: "Does the signal price returns, and is the model well specified?", features: ["01"] },
  { id: "robustness", label: "Robustness", icon: GitFork, question: "Does it survive other choices, fake signals and other regimes?", features: ["02", "03"] },
  { id: "causal", label: "Causal", icon: Crosshair, question: "Is the effect causal, from DiD to synthetic control?", features: ["07"] },
  { id: "decay", label: "Decay & novelty", icon: Hourglass, question: "Is it fading, and is it new or a known factor?", features: ["08"] },
];
/** Features now shown inside another page (backend merges); their old URLs still open on their own. */
export const RESEARCH_MERGED: Record<string, string> = { "05": "01", "04": "02", "09": "07", "11": "08", "06": "01" };

export const metaFor = (id: string, fallbackName = "") => lab().catalog[id] ?? { name: fallbackName, slug: `f${id}`, icon: Sigma, question: "" };

export const featureHref = (id: string) => `${lab().root}/${metaFor(id).slug}`;

export const idFromSlug = (slug: string | undefined): string | null => {
  if (!slug) return null;
  const hit = Object.entries(lab().catalog).find(([, m]) => m.slug === slug);
  if (hit) return hit[0];
  return /^f\d{2}$/.test(slug) ? slug.slice(1) : null;
};

export const pageOf = (featureId: string | null) => {
  if (!featureId) return null;
  const via = lab().merged?.[featureId] ?? "";
  return lab().pages.find((p) => p.features.includes(featureId) || p.features.includes(via)) ?? null;
};
export const pageHref = (p: Page) => (p.slug ? `${lab().root}/${p.slug}` : featureHref(p.features[0]));
export const specialPage = (slug: string | undefined) => lab().pages.find((p) => p.slug && p.slug === slug) ?? null;
