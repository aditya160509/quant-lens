"use client";

import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

export default class StudioPaneBoundary extends React.Component {
    state = { error: null };

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidUpdate(previousProps) {
        if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
            this.setState({ error: null });
        }
    }

    render() {
        if (!this.state.error) return this.props.children;

        return (
            <div role="alert" className="flex min-h-0 flex-1 items-center justify-center bg-[#020204] p-8">
                <div className="w-full max-w-lg border-l-2 border-red-500 bg-red-500/[0.04] px-6 py-5">
                    <div className="mb-2 flex items-center gap-2 text-red-300">
                        <AlertTriangle size={16} />
                        <h2 className="text-xs font-bold uppercase tracking-[0.18em]">Workspace pane failed</h2>
                    </div>
                    <p className="mb-4 text-xs leading-relaxed text-slate-400">
                        This pane could not render. Other Studio state remains intact.
                    </p>
                    <button
                        type="button"
                        onClick={() => this.setState({ error: null })}
                        className="inline-flex h-8 items-center gap-2 border border-white/10 bg-white/[0.04] px-3 text-[10px] font-bold uppercase tracking-wider text-slate-200 hover:border-amber-400/40 hover:text-amber-300"
                    >
                        <RotateCcw size={12} /> Retry pane
                    </button>
                </div>
            </div>
        );
    }
}
