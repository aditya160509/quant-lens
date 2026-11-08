"use client";

import { ResearchApp } from "@/modules/research/ResearchApp";
import { SCREENER_LAB } from "./screenerLab";

export function ScreenerApp() {
  return <ResearchApp config={SCREENER_LAB} />;
}
