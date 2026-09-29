'use client';

/**
 * Signals Tab - Command Grid Architecture
 * High-density tactical environment with Neural Dependency Maps
 */

import React from 'react';
import dynamic from 'next/dynamic';

// Dynamically load the Command Grid to ensure canvas/physics engine runs client-side only
const CommandGrid = dynamic(() => import('../command_grid/CommandGrid'), { 
    ssr: false, 
    loading: () => (
        <div className="h-full w-full flex flex-col items-center justify-center bg-[#02040a]">
            <div className="text-violet-500 font-mono text-[10px] animate-pulse tracking-[0.5em] uppercase mb-4">Initializing Command Core...</div>
            <div className="w-48 h-1 bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-violet-500 w-1/3 animate-[loading_2s_infinite_linear]" />
            </div>
            <style jsx>{`
                @keyframes loading {
                    0% { transform: translateX(-100%); }
                    100% { transform: translateX(300%); }
                }
            `}</style>
        </div>
    )
});

export default function SignalsTab() {
    return (
        <div className="h-full w-full bg-terminal-black">
            <CommandGrid />
        </div>
    );
}
