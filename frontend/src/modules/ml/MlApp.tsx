"use client";

import { ResearchApp } from "@/modules/research/ResearchApp";
import "./ml.css";
import { ML_LAB } from "./mlLab";

/** Machine learning runs on the shared lab workspace with its own catalog, API and views. */
export function MlApp() {
  return <ResearchApp config={ML_LAB} />;
}
