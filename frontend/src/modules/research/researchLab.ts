import { API_BASE_URL } from "@/lib/apiBase";
import { RESEARCH_CATALOG, RESEARCH_MERGED, RESEARCH_PAGES } from "./catalog";
import type { LabConfig } from "./lab";
import type { FeatureSpec } from "./types";

export const RESEARCH_LAB: LabConfig = {
  id: "research",
  title: "Research",
  root: "/research",
  base: `${API_BASE_URL}/labs/research/v2`,
  catalog: RESEARCH_CATALOG,
  pages: RESEARCH_PAGES,
  merged: RESEARCH_MERGED,
  manifest: (raw) => (raw as { features: FeatureSpec[] }).features,
  submit: (featureId, payload) => ({ path: `/feature/${featureId}/jobs`, body: { payload } }),
  signal: true,
};
