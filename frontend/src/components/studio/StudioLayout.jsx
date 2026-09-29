"use client";
import React, { useState } from 'react';
import LayoutManagerModal from './LayoutManagerModal';
import StudioActivityRail from './shell/StudioActivityRail';
import ExecutionAssumptionsPanel from './shell/ExecutionAssumptionsPanel';
import DataInspectorPanel from './shell/DataInspectorPanel';
import StudioContextToolbar from './shell/StudioContextToolbar';
import StudioModeStage from './shell/StudioModeStage';
import { useStudioLayoutStore } from '@/stores/studio/layoutStore';

const StudioLayout = () => {
    const showLayoutManager = useStudioLayoutStore((s) => s.showLayoutManager);
    const setShowLayoutManager = useStudioLayoutStore((s) => s.setShowLayoutManager);
    const [showSettings, setShowSettings] = useState(false);
    const [showData, setShowData] = useState(false);
    return (
        <div className="flex-1 flex min-h-0 bg-[#020204]">
            <StudioActivityRail settingsOpen={showSettings} onToggleSettings={() => { setShowSettings((open) => !open); setShowData(false); }} dataOpen={showData} onToggleData={() => { setShowData((open) => !open); setShowSettings(false); }} />
            <div className="flex-1 flex flex-col min-w-0 relative">
                <StudioContextToolbar />
                <div className="flex-1 flex min-h-0 overflow-hidden relative">
                    {showSettings && <ExecutionAssumptionsPanel onClose={() => setShowSettings(false)} />}
                    {showData && <DataInspectorPanel onClose={() => setShowData(false)} />}
                    <StudioModeStage />
                    <LayoutManagerModal isOpen={showLayoutManager} onClose={() => setShowLayoutManager(false)} />
                </div>
            </div>
        </div>
    );
};

export default StudioLayout;
