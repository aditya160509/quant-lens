import { Suspense, type ReactNode } from "react";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { WorkspaceShell } from "@/workspace/WorkspaceShell";
import { ResearchApp } from "@/modules/research/ResearchApp";

export const metadata = { title: "Research · ATLAS" };

/** The workspace renders the whole module; route segments only select the feature. */
export default function ResearchLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceShell module="research" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <Suspense>
        <ResearchApp />
      </Suspense>
      {children}
    </WorkspaceShell>
  );
}
