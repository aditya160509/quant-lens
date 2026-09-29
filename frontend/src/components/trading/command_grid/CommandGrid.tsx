'use client';

import React from 'react';
import HUDContainer from './HUDContainer';
import DependencyMap from './DependencyMap';
import CauseEngine from './CauseEngine';
import SignalSummary from './SignalSummary';
import ImpactMatrix from './ImpactMatrix';
import QuickTradePanel from './QuickTradePanel';
import { Activity, Brain, Zap } from 'lucide-react';

export default function CommandGrid() {
    return (
        <div className="h-full w-full bg-[#02040a] p-2 flex flex-col gap-2 select-none overflow-hidden">

            {/* Main Content: 12-Column Grid */}
            <div className="flex-1 min-h-0 w-full grid grid-cols-12 gap-2">
                
                {/* Left Panel: Cause Engine (Cols 1-3) */}
                <div className="col-span-3 h-full">
                    <HUDContainer 
                        title="Cause Engine" 
                        icon={<Activity size={12} />}
                        className="h-full"
                    >
                        <CauseEngine />
                    </HUDContainer>
                </div>

                {/* Center Panel: Dependency Map (Cols 4-9) */}
                <div className="col-span-6 h-full">
                    <HUDContainer 
                        title="Neural Dependency Map" 
                        icon={<Brain size={12} />}
                        className="h-full bg-black/60 shadow-[inset_0_0_100px_rgba(139,92,246,0.05)]"
                    >
                        <DependencyMap />
                    </HUDContainer>
                </div>

                {/* Right Panel: Impact Matrix (Cols 10-12) */}
                <div className="col-span-3 h-full">
                    <HUDContainer 
                        title="Impact Matrix" 
                        icon={< Zap size={12} />}
                        className="h-full"
                    >
                        <ImpactMatrix />
                    </HUDContainer>
                </div>

            </div>

            {/* Global Scanline Effect */}
            <div className="fixed inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] z-50 bg-[length:100%_2px,3px_100%]" />
        </div>
    );
}
