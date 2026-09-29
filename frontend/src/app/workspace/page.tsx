'use client';

import { Suspense } from 'react';
import dynamic from 'next/dynamic';

// Dynamic import for the main workspace component
const SovereignWorkspace = dynamic(
  () => import('@/components/sovereign/SovereignWorkspace'),
  { 
    ssr: false, 
    loading: () => (
      <div className="h-screen w-screen flex items-center justify-center bg-terminal-black">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-terminal-gray rounded-full animate-pulse" />
            <div className="absolute inset-0 w-16 h-16 border-4 border-t-terminal-yellow rounded-full animate-spin" />
          </div>
          <div className="text-terminal-dim font-mono text-sm tracking-wider">
            INITIALIZING WORKSPACE...
          </div>
        </div>
      </div>
    )
  }
);

/**
 * 🛰️ SOVEREIGN WORKSPACE PAGE
 * The Command-and-Control Hub - Bloomberg-grade modular workstation
 * 
 * Route: /workspace
 */
export default function WorkspacePage() {
  return (
    <Suspense fallback={
      <div className="h-screen w-screen flex items-center justify-center bg-terminal-black">
        <div className="text-terminal-dim font-mono text-sm">Loading Workspace...</div>
      </div>
    }>
      <SovereignWorkspace />
    </Suspense>
  );
}
