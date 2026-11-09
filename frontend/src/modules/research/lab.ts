import type { LucideIcon } from "lucide-react";
import type { ComponentType } from "react";
import type { FeatureLayout } from "./layouts";
import type { FeatureResult, FeatureSpec, InputSpec, RunRecord } from "./types";

/**
 * One workspace engine serves several labs (Research, Machine learning). A lab supplies its API,
 * catalog, pages and layouts; everything else (nav, forms, cards, view-as, dock, runs) is shared.
 * Feature ids are unique across labs (ML ids carry an "ml" prefix), so runs, card preferences and
 * saved forms never collide in the shared stores.
 */
export type FeatureMeta = { name: string; slug: string; icon: LucideIcon; question: string };
export type Page = { id: string; label: string; icon: LucideIcon; question: string; features: string[]; slug?: string };

export type LabConfig = {
  id: string;
  title: string;
  /** Route root, e.g. "/research". */
  root: string;
  /** API base for manifest and jobs. */
  base: string;
  catalog: Record<string, FeatureMeta>;
  pages: Page[];
  /** Features shown inside another feature's page. */
  merged?: Record<string, string>;
  layouts?: Record<string, FeatureLayout>;
  /** The /features response as specs. */
  manifest: (raw: unknown) => FeatureSpec[];
  /** Request that starts a job for a feature. */
  submit: (featureId: string, payload: Record<string, unknown>) => { path: string; body: unknown };
  /** Overview intro and the ordered stages its feature cards are grouped into. */
  overview?: {
    /** Replaces the whole overview page. */
    home?: ComponentType<{ features: FeatureSpec[]; runs: RunRecord[] }>;
    intro: string;
    stages: { id: string; label: string; intro: string; ids: string[] }[];
    /** Large "start here" tiles above the stages; each shows its feature's latest verdict once it has run. */
    actions?: { id: string; title: string; body: string; cta: string }[];
    /** Replaces the start tiles once any of them has a finished run: the latest answer from each page. */
    today?: ComponentType<{ features: FeatureSpec[]; runs: RunRecord[] }>;
    /** Words for the headline counts, e.g. "Held up" instead of "Pass". */
    words?: { tests: string; pass: string; mixed: string; fail: string };
  };
  /** A custom control for an input, keyed by the input's key. */
  widgets?: Record<string, ComponentType<{ field: InputSpec; value: unknown; onChange: (v: unknown) => void }>>;
  /** Per-filter counts from a finished run, keyed by the filter's metric name. */
  funnel?: (result: FeatureResult | undefined) => Record<string, { removed: number; remaining: number; bottleneck?: boolean }>;
  /** What an empty ticker list means for this lab, shown in the Universe chip. */
  defaultUniverse?: string;
  /** Pages with their own component instead of a feature, keyed by Page.id (needs Page.slug). The "verified" key
   * also serves /<root>/verified/[id], with the id passed in. */
  specials?: Record<string, ComponentType<{ features: FeatureSpec[]; id?: string }>>;
  /** Exhibit titles that state the finding; null keeps the descriptive title. Labs that set it also number their exhibits. */
  takeaway?: (featureId: string, key: string, view: string | undefined, result: FeatureResult) => string | null;
  /** Verb on the run button for a feature, e.g. "Train and test"; defaults to "Run study". */
  runLabel?: (featureId: string) => string;
  /** Research extras: Signal and Report card pages, projects, ledger, active signal. */
  signal: boolean;
};

let current: LabConfig | null = null;

export function setLab(config: LabConfig) {
  current = config;
}

export function lab(): LabConfig {
  if (!current) throw new Error("No lab is mounted");
  return current;
}

/** True when the id belongs to the mounted lab, so background polling never asks the wrong API. */
export const owns = (featureId: string) => Boolean(current && featureId in current.catalog);

/** The run button's verb for a feature in the mounted lab. */
export const runLabel = (featureId: string) => current?.runLabel?.(featureId) ?? "Run study";
