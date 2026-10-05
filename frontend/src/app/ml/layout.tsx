import { Suspense, type ReactNode } from "react";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { WorkspaceShell } from "@/workspace/WorkspaceShell";
import { MlApp } from "@/modules/ml/MlApp";

export const metadata = { title: "Machine learning · ATLAS" };

/** The shared workspace renders the whole module; route segments only select the feature. */
export default function MlLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceShell module="ml" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <Suspense>
        <MlApp />
      </Suspense>
      {children}
    </WorkspaceShell>
  );
}
