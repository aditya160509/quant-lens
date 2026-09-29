"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["08"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // EXPORT LAYER",
  headline: "Package screen results for downstream workflows.",
  description: "Download-ready payloads, API endpoint metadata and change reports designed for Excel, notebooks and automation handoff.",
  intent: "export · integrate · audit",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="08" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
