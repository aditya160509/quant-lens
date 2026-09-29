"use client";

import React, { useRef } from 'react';
import { LayoutGrid, X } from 'lucide-react';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { useStudioLayoutStore } from '@/stores/studio/layoutStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import { useStudioModalA11y } from './shell/useStudioModalA11y';

const LAYOUT_OPTIONS = [
    { id: '1x1', label: 'Single', cells: 1 },
    { id: '1x2', label: 'Split vertical', cells: 2 },
    { id: '2x1', label: 'Split horizontal', cells: 2 },
    { id: '2x2', label: 'Quad', cells: 4 },
    { id: '2x3', label: 'Six grid', cells: 6 },
    { id: '3x3', label: 'Nine grid', cells: 9 },
    { id: '4x4', label: 'Sixteen grid', cells: 16 },
];

export default function LayoutManagerModal({ isOpen, onClose }) {
    const ticker = useStudioWorkspaceStore((state) => state.ticker);
    const addTickerToLayout = useStudioLayoutStore((state) => state.addTickerToLayout);
    const gridConfig = useStudioLayoutStore((state) => state.gridConfig);
    const layoutInitState = useStudioLayoutStore((state) => state.layoutInitState);
    const resetLayoutInitialization = useStudioLayoutStore((state) => state.resetLayoutInitialization);
    const startLayout = useStudioLayoutStore((state) => state.startLayoutInitialization);
    const isSelectingTickers = layoutInitState.isActive;
    const close = () => {
        resetLayoutInitialization();
        onClose?.();
    };
    const dialogRef = useRef(null);
    const { onKeyDownTrap } = useStudioModalA11y({ isOpen: isOpen || isSelectingTickers, onClose: close, dialogRef });

    if (!isOpen && !isSelectingTickers) return null;

    const selectTicker = (ticker) => {
        const completesLayout = layoutInitState.pendingTickers.length + 1 >= layoutInitState.total;
        addTickerToLayout(ticker);
        if (completesLayout) onClose?.();
    };

    return (
        <div className="fixed inset-0 z-[320] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={close} />
            <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="layout-manager-title" onKeyDown={onKeyDownTrap} className="relative w-full max-w-lg space-y-5 overflow-visible rounded-2xl border border-white/10 bg-[#0a0a0f] p-6 shadow-2xl">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                        <LayoutGrid size={15} className="mt-0.5 text-amber-500" />
                        <div>
                            <h3 id="layout-manager-title" className="text-[12px] font-bold uppercase tracking-widest text-white">
                                {isSelectingTickers
                                    ? `Chart ${layoutInitState.step + 1} of ${layoutInitState.total}`
                                    : 'Chart layout'}
                            </h3>
                            <p className="mt-1 text-[10px] font-mono leading-relaxed text-[#64748b]">
                                {isSelectingTickers
                                    ? 'Choose an observed ticker for each remaining panel.'
                                    : 'Choose a panel arrangement. Multi-panel layouts request one ticker per slot.'}
                            </p>
                        </div>
                    </div>
                    <button onClick={close} aria-label="Close layout manager" className="rounded p-2 text-[#64748b] hover:bg-white/5 hover:text-white">
                        <X size={16} />
                    </button>
                </div>

                {isSelectingTickers ? (
                    <>
                        <div className="relative z-[330]">
                            <TradingViewSearch
                                onSelect={selectTicker}
                                placeholder="SEARCH TICKER..."
                                autoFocus
                                dropdownZIndex={340}
                            />
                        </div>
                        <div className="space-y-3 border-t border-white/5 pt-4">
                            <span className="text-[9px] font-mono uppercase tracking-widest text-[#64748b]">Current selection</span>
                            <div className="flex flex-wrap gap-2">
                                {layoutInitState.pendingTickers.map((ticker, index) => (
                                    <div key={`${ticker}-${index}`} className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5">
                                        <span className="text-[10px] font-mono font-bold text-amber-500">{index + 1}</span>
                                        <span className="text-[10px] font-mono text-white">{ticker}</span>
                                    </div>
                                ))}
                                <div className="flex items-center gap-2 rounded-lg border border-dashed border-amber-500/20 bg-amber-500/10 px-3 py-1.5">
                                    <span className="text-[10px] font-mono font-bold text-amber-500">{layoutInitState.step + 1}</span>
                                    <span className="text-[10px] font-mono text-amber-500/60">Pending</span>
                                </div>
                            </div>
                        </div>
                        <button onClick={close} className="w-full rounded-xl border border-white/10 py-3 text-[10px] font-mono font-bold uppercase tracking-widest text-[#64748b] hover:bg-white/5">
                            Cancel layout setup
                        </button>
                    </>
                ) : (
                    <div className="grid grid-cols-4 gap-2">
                        {LAYOUT_OPTIONS.map((layout) => {
                            const active = gridConfig.layoutId === layout.id;
                            return (
                                <button
                                    key={layout.id}
                                    onClick={() => {
                                        startLayout(layout.id, ticker);
                                        if (layout.cells === 1) onClose?.();
                                    }}
                                    title={`${layout.label} (${layout.cells} charts)`}
                                    className={`h-14 rounded-lg border text-[10px] font-mono font-bold uppercase tracking-wider transition-colors ${active ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-white/10 bg-white/[0.02] text-[#9aa4b2] hover:border-white/20 hover:text-white'}`}
                                >
                                    <div>{layout.id}</div>
                                    <div className="text-[8px] opacity-70">{layout.cells} charts</div>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
