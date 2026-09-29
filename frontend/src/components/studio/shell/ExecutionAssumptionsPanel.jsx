"use client";

import { Settings, X } from "lucide-react";
import { useStudioWorkspaceStore } from "@/stores/studio/workspaceStore";

export default function ExecutionAssumptionsPanel({ onClose }) {
    const slippageBps = useStudioWorkspaceStore((state) => state.slippageBps);
    const setSlippageBps = useStudioWorkspaceStore((state) => state.setSlippageBps);
    const commissionPct = useStudioWorkspaceStore((state) => state.commissionPct);
    const setCommissionPct = useStudioWorkspaceStore((state) => state.setCommissionPct);

    return (
        <section
            id="studio-execution-assumptions"
            aria-label="Execution assumptions"
            className="absolute right-2 top-2 z-40 w-64 rounded-xl border border-white/10 bg-[#0a0a0f]/95 p-4 shadow-2xl backdrop-blur-xl"
        >
            <div className="mb-4 flex items-center justify-between">
                <h2 className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-amber-500">
                    <Settings size={10} /> Execution assumptions
                </h2>
                <button
                    type="button"
                    onClick={onClose}
                    className="rounded p-1 text-[#64748b] transition-colors hover:bg-white/5 hover:text-white"
                    aria-label="Close execution assumptions"
                >
                    <X size={12} />
                </button>
            </div>

            <div className="space-y-4">
                <label className="block">
                    <span className="mb-1 flex justify-between font-mono text-[9px] text-[#64748b]">
                        <span>SLIPPAGE</span>
                        <span className="text-white">{slippageBps} BPS</span>
                    </span>
                    <input
                        type="range"
                        aria-label="Slippage basis points"
                        min={0}
                        max={20}
                        step={0.5}
                        value={slippageBps}
                        onChange={(event) => setSlippageBps(Number(event.target.value))}
                        className="h-1 w-full accent-amber-500"
                    />
                </label>

                <label className="block">
                    <span className="mb-1 flex justify-between font-mono text-[9px] text-[#64748b]">
                        <span>COMMISSION</span>
                        <span className="text-white">{commissionPct}%</span>
                    </span>
                    <input
                        type="range"
                        aria-label="Commission percent"
                        min={0}
                        max={0.5}
                        step={0.01}
                        value={commissionPct}
                        onChange={(event) => setCommissionPct(Number(event.target.value))}
                        className="h-1 w-full accent-amber-500"
                    />
                </label>

                <p className="border-t border-white/5 pt-3 font-mono text-[8px] leading-relaxed text-[#64748b]">
                    Applied to the next strategy execution request. These values do not modify completed runs.
                </p>
            </div>
        </section>
    );
}
