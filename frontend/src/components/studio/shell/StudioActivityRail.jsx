"use client";

import { Database, Settings, Terminal } from "lucide-react";
import { useStudioPreferenceStore } from "@/stores/studio/preferenceStore";

export default function StudioActivityRail({ settingsOpen, onToggleSettings, dataOpen, onToggleData }) {
    const kernelCollapsed = useStudioPreferenceStore((state) => state.kernelCollapsed);
    const setKernelCollapsed = useStudioPreferenceStore((state) => state.setKernelCollapsed);

    return (
        <aside
            aria-label="Studio tools"
            className="relative z-50 flex w-11 flex-shrink-0 flex-col overflow-visible border-r border-white/5 bg-[#0a0a0f]"
        >
            <div className="flex flex-col items-center gap-4 py-4">
                <button
                    type="button"
                    onClick={() => setKernelCollapsed(!kernelCollapsed)}
                    className={`rounded-lg p-2 transition-colors ${!kernelCollapsed ? "bg-amber-500/5 text-amber-500" : "text-[#64748b] hover:text-white"}`}
                    aria-pressed={!kernelCollapsed}
                    aria-label="Toggle strategy editor"
                    title="Toggle strategy editor"
                >
                    <Terminal size={20} />
                </button>
                <div className="h-px w-6 bg-white/5" aria-hidden="true" />
                <button type="button" onClick={onToggleData} className={`rounded-lg p-2 transition-colors ${dataOpen ? "bg-amber-500/5 text-amber-500" : "text-[#64748b] hover:text-white"}`} aria-expanded={dataOpen} aria-controls="studio-data-inspector" aria-label="Toggle data inspector" title="Data inspector"><Database size={20} /></button>
            </div>

            <div className="mt-auto flex flex-col items-center gap-2 border-t border-white/5 py-2">
                <button
                    type="button"
                    onClick={onToggleSettings}
                    className={`rounded-lg p-2 transition-colors ${settingsOpen ? "bg-amber-500/5 text-amber-500" : "text-[#64748b] hover:text-white"}`}
                    aria-expanded={settingsOpen}
                    aria-controls="studio-execution-assumptions"
                    aria-label="Toggle execution assumptions"
                    title="Execution assumptions"
                >
                    <Settings size={20} />
                </button>
            </div>
        </aside>
    );
}
