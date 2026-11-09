import { Suspense, type ReactNode } from "react";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { WorkspaceShell } from "@/workspace/WorkspaceShell";
import { ScreenerApp } from "@/modules/screener/ScreenerApp";

export const metadata = { title: "Screener · ATLAS" };

/** The shared workspace renders the whole module; route segments only select the feature. */
export default function ScreenerLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceShell module="screener" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <NuqsAdapter>
        <Suspense>
          <ScreenerApp />
        </Suspense>
        {children}
      </NuqsAdapter>
    </WorkspaceShell>
  );
}
