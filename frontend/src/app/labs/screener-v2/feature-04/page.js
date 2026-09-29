"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["04"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // ACADEMIC STRATEGIES",
  headline: "Compare academic screens like a production strategy book.",
  description: "Strategy leaderboard, per-strategy stock lists, Piotroski and Altman detail, strategy correlation and historical performance outputs.",
  intent: "strategy library · diagnostics",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="04" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
