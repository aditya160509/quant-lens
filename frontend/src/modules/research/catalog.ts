import { CloudLightning, Crosshair, GitFork, Hourglass, Layers, PawPrint, ShieldCheck, Sigma, Stethoscope, Table2, type LucideIcon } from "lucide-react";

/** How each feature is presented: a short name, an icon and the question it answers. Keyed by backend feature id. */
export const CATALOG: Record<string, { name: string; slug: string; icon: LucideIcon; question: string }> = {
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

export const metaFor = (id: string, fallbackName = "") => CATALOG[id] ?? { name: fallbackName, slug: `f${id}`, icon: Sigma, question: "" };

export const featureHref = (id: string) => `/research/${metaFor(id).slug}`;

export const idFromSlug = (slug: string | undefined): string | null => {
  if (!slug) return null;
  const hit = Object.entries(CATALOG).find(([, m]) => m.slug === slug);
  if (hit) return hit[0];
  return /^f\d{2}$/.test(slug) ? slug.slice(1) : null;
};
