"use client";
import React, { Suspense, lazy } from 'react';
import StudioPaneBoundary from '../StudioPaneBoundary';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import './studioA11y.css';

// P15: lazy-load Studio mode surfaces so the initial Studio bundle only
// pays for the active mode. Validate/Stress stay eager because they share
// the ValidationWorkspace chrome and its focused test gate.
const DevelopView = lazy(() => import('../DevelopView'));
const StressView = lazy(() => import('../StressView'));
const ValidateView = lazy(() => import('../ValidateView'));
const ReplayView = lazy(() => import('../ReplayView'));
const TearsheetView = lazy(() => import('../TearsheetView'));
const PortfolioView = lazy(() => import('../PortfolioView'));
const PaperView = lazy(() => import('../PaperView'));
const ComposerView = lazy(() => import('../ComposerView'));
const AdvancedValidationView = lazy(() => import('../AdvancedValidationView'));

function ModeFallback() {
    return (
        <div role="status" aria-label="Loading workspace mode" className="flex min-h-0 flex-1 items-center justify-center bg-[#050812]">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">Loading mode…</span>
        </div>
    );
}

export default function StudioModeStage() {
    const activeTab = useStudioWorkspaceStore((s) => s.activeTab);
    return (
        <StudioPaneBoundary resetKey={activeTab}>
            <Suspense fallback={<ModeFallback />}>
                {activeTab === 'develop' && <DevelopView />}
                {activeTab === 'tearsheet' && <TearsheetView />}
                {activeTab === 'portfolio' && <PortfolioView />}
                {activeTab === 'paper' && <PaperView />}
                {activeTab === 'composer' && <ComposerView />}
                {activeTab === 'validate' && <ValidationWorkspace />}
                {activeTab === 'replay' && <ReplayView />}
            </Suspense>
        </StudioPaneBoundary>
    );
}

function ValidationWorkspace() {
    const [surface, setSurface] = React.useState('walk-forward');
    return <div className="flex min-h-0 flex-1 flex-col bg-[#050812]">
        <nav aria-label="Validation methods" className="flex h-10 shrink-0 items-center gap-1 border-b border-white/10 bg-[#080c14] px-6">
            {[['walk-forward', 'Walk-forward'], ['monte-carlo', 'Monte Carlo stress'], ['advanced', 'Advanced evidence']].map(([id, label]) => <button key={id} type="button" aria-pressed={surface === id} onClick={() => setSurface(id)} className={`h-7 px-3 text-[10px] font-mono font-bold uppercase tracking-wider ${surface === id ? 'bg-amber-400 text-black' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}>{label}</button>)}
        </nav>
        {surface === 'walk-forward' ? <ValidateView /> : surface === 'monte-carlo' ? <StressView /> : <AdvancedValidationView />}
    </div>;
}
