"use client";

import { ResearchApp } from "@/modules/research/ResearchApp";
import { STUDIO_LAB } from "./studioLab";

export function StudioApp() {
  return <ResearchApp config={STUDIO_LAB} />;
}
