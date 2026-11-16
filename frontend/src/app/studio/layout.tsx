import { Suspense, type ReactNode } from "react";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { WorkspaceShell } from "@/workspace/WorkspaceShell";
import { StudioApp } from "@/modules/studio/StudioApp";

export const metadata = { title: "Studio · ATLAS" };

/** The shared workspace renders the whole module; route segments only select the page. */
export default function StudioLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceShell module="studio" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <NuqsAdapter>
        <Suspense>
          <StudioApp />
        </Suspense>
        {children}
      </NuqsAdapter>
    </WorkspaceShell>
  );
}
