import React, { useEffect, useState } from 'react';
import { getGameStatus } from '@/lib/api';

export default function GamificationRibbon() {
    const [status, setStatus] = useState(null);

    useEffect(() => {
        loadStatus();
        // Poll every 30s
        const interval = setInterval(loadStatus, 30000);
        return () => clearInterval(interval);
    }, []);

    const loadStatus = async () => {
        try {
            const data = await getGameStatus();
            setStatus(data);
        } catch (e) {
            console.error("Failed to load game status", e);
        }
    };

    if (!status) return null;

    return (
        <div className="flex items-center gap-4 bg-terminal-darker border-b border-terminal-dark-gray px-6 py-2 text-sm font-mono">
            <div className="text-terminal-gold">
                <span className="text-terminal-dim mr-2">XP</span>
                <span className="font-bold">{status.score}</span>
            </div>
            <div className="h-4 w-px bg-terminal-dark-gray"></div>
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
                {status.badges.map((badge, i) => (
                    <div key={i} className="flex items-center gap-1 bg-terminal-dark px-2 py-0.5 rounded border border-terminal-dark-gray text-xs text-terminal-text whitespace-nowrap" title={badge.desc}>
                        <span>🏆</span>
                        <span>{badge.name}</span>
                    </div>
                ))}
                {status.badges.length === 0 && (
                    <span className="text-terminal-dim italic text-xs">No badges yet. Start trading!</span>
                )}
            </div>
        </div>
    );
}
