"use client";

import { ResearchApp } from "@/modules/research/ResearchApp";
import { SCREENER_LAB } from "./screenerLab";
import { UrlState } from "./UrlState";

export function ScreenerApp() {
  return (
    <>
      <UrlState />
      <ResearchApp config={SCREENER_LAB} />
    </>
  );
}
