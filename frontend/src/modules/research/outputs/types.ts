import type { FeatureResult, FeatureSpec, OutputSpec, Row } from "../types";

/** Every view gets the whole result so it can combine outputs; `rows` is the primary output's rows. */
export type ViewProps = {
  rows: Row[];
  result: FeatureResult;
  feature: FeatureSpec;
  spec?: OutputSpec;
  /** Output keys this view draws from (the first is the primary). */
  keys: string[];
  /** Per-layout options, e.g. which column to plot. */
  opts?: Record<string, unknown>;
  /** Persist chart notes under this scope. */
  scope: string;
};
