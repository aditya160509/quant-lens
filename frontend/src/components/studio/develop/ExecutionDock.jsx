"use client";
/* eslint-disable react-hooks/set-state-in-effect -- execution dock log append is effect intent */
import React, { useEffect, useRef, useState } from 'react';
import { Terminal, Activity, Clock, X, Trash2, Play } from 'lucide-react';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioEditorStore } from '@/stores/studio/editorStore';
import { useStudioExecution, STUDIO_QUOTAS, estimateComputeQuota } from '@/hooks/studio/useStudioExecution';
import { studioRequest } from '@/lib/studioApi';
import { isStudioHealthResponse } from '@/lib/studioValidators';

const VARS_PAGE_SIZE = 50;
export const VARIABLES_PAGE_SIZE = VARS_PAGE_SIZE;

// Pure: paginate an array variable into { page, totalPages, items }.
export function paginateVariable(items, page, pageSize = VARS_PAGE_SIZE) {
    const list = Array.isArray(items) ? items : [];
    const totalPages = Math.max(1, Math.ceil(list.length / pageSize));
    const safePage = Math.min(Math.max(0, page), totalPages - 1);
    return { page: safePage, totalPages, total: list.length, items: list.slice(safePage * pageSize, (safePage + 1) * pageSize) };
}

export default function ExecutionDock() {
    const isExecuting = useStudioResultStore((s) => s.isExecuting);
    const executionError = useStudioResultStore((s) => s.executionError);
    const data = useStudioResultStore((s) => s.data);
    const codeA = useStudioEditorStore((s) => s.codeA);
    const selectedCode = useStudioEditorStore((s) => s.selectedCode);
    const { executeSelection } = useStudioExecution();
    const [logs, setLogs] = useState([]);
    const [elapsed, setElapsed] = useState(0);
    const [environment, setEnvironment] = useState(STUDIO_QUOTAS.executionMode);
    const [health, setHealth] = useState(null);
    const [expanded, setExpanded] = useState(null);
    const [varPage, setVarPage] = useState({});
    const logRef = useRef(null);

    useEffect(() => {
        let cancelled = false;
        studioRequest('/health', { validate: isStudioHealthResponse })
            .then((h) => { if (!cancelled) { setHealth(h); setLogs((l) => [...l, `[env] backend reports mode=${h?.execution?.mode || 'unknown'} readiness=${h?.execution?.readiness || 'unknown'}`]); } })
            .catch((e) => { if (!cancelled) setLogs((l) => [...l, `[env] health check failed: ${e?.message || 'unknown error'} — showing limits from conventions`]); });
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        if (!isExecuting) { setElapsed(0); return; }
        const start = Date.now();
        const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 200);
        setLogs((l) => [...l, `[${new Date().toISOString()}] execution request submitted (env=${environment})`]);
        return () => clearInterval(id);
    }, [isExecuting, environment]);

    useEffect(() => {
        if (executionError) setLogs((l) => [...l, `[error] ${executionError}`]);
        if (data?.metadata?.provenance) setLogs((l) => [...l, `[provenance] ${data.metadata.provenance.engine_version} code_hash=${data.metadata.provenance.code_hash?.slice(0, 8) || '--'}`]);
        if (data?.metadata?.selection) setLogs((l) => [...l, `[selection] selection job completed run=${data?.runId || '--'}`]);
    }, [executionError, data?.metadata, data?.runId]);

    useEffect(() => { logRef.current?.scrollTo(0, logRef.current.scrollHeight); }, [logs]);

    const quota = estimateComputeQuota(codeA);
    const resources = data?.metadata?.resources || data?.resources || null;

    const vars = [
        { name: 'data', type: `DataFrame[${data?.candles?.length || 0} rows]`, preview: data?.candles?.[0] ? `${data.candles[0].close}` : '--', rows: data?.candles || [] },
        { name: 'signals', type: `list[${data?.signals?.length || 0}]`, preview: data?.signals?.[0]?.direction ?? '--', rows: data?.signals || [] },
        { name: 'equityCurve', type: `list[${data?.equityCurve?.length || 0}]`, preview: data?.equityCurve?.[0] ?? '--', rows: data?.equityCurve || [] },
        { name: 'trades', type: `list[${data?.trades?.length || 0}]`, preview: data?.trades?.[0]?.pnl ?? '--', rows: data?.trades || [] },
        { name: 'metrics', type: 'dict', preview: data?.metrics?.sharpe != null ? `sharpe=${Number(data.metrics.sharpe).toFixed(2)}` : '--', rows: Object.entries(data?.metrics || {}).map(([k, v]) => ({ key: k, value: v })) },
    ];

    const handleRunSelection = () => {
        setLogs((l) => [...l, `[selection] submitting ${(selectedCode || '').length} chars as execute job (source=selection, env=${environment})`]);
        executeSelection(selectedCode);
    };

    return (
        <div className="h-[180px] border-t border-white/5 bg-[#050508] flex">
            <div className="flex-1 flex flex-col border-r border-white/5 min-w-0">
                <div className="h-7 px-3 border-b border-white/5 flex items-center justify-between bg-[#0a0a0f]">
                    <div className="flex items-center gap-2">
                        <Terminal size={12} className="text-amber-500" />
                        <span className="text-[10px] font-mono font-bold tracking-widest text-white">EXECUTION DOCK</span>
                        <span className={`text-[8px] font-mono px-2 py-0.5 rounded border ${isExecuting ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' : 'bg-white/5 text-[#8b95a7] border-white/10'}`}>{isExecuting ? `REQUESTING ${elapsed}s` : 'NOT RUNNING'}</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <button aria-label="Run selection" title={selectedCode ? `Run ${(selectedCode || '').length} selected chars as a selection job` : 'Select code in the editor first'} onClick={handleRunSelection} disabled={isExecuting || !selectedCode} className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono text-amber-400 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed"><Play size={10} />SELECTION</button>
                        <button aria-label="Clear logs" onClick={() => setLogs([])} className="p-1 hover:bg-white/10 rounded text-[#64748b]"><Trash2 size={12} /></button>
                    </div>
                </div>
                {/* Env picker + quota + telemetry strip (P5-W2 polish) */}
                <div className="px-3 py-1 border-b border-white/5 flex items-center gap-3 bg-black/30 text-[9px] font-mono text-[#64748b] overflow-x-auto whitespace-nowrap">
                    <label className="flex items-center gap-1.5">
                        <span>ENV</span>
                        <select aria-label="Execution environment" value={environment} onChange={(e) => setEnvironment(e.target.value)} className="bg-black/50 border border-white/10 rounded px-1 py-0.5 text-white">
                            <option value="isolated_one_shot">local · isolated_one_shot</option>
                            <option value="container">container · not reported</option>
                        </select>
                    </label>
                    <span title="Backend health">{health ? `health: ${health.execution?.mode || '?'} / ${health.execution?.readiness || '?'}` : 'health: checking…'}</span>
                    {environment === 'container' && <span className="text-amber-400">container runtime not reported by /health — jobs still run on isolated_one_shot</span>}
                    <span title="Client-side quota estimate">quota: {quota.codeBytes}B ({quota.codeBytesPct}% of {STUDIO_QUOTAS.maxCodeBytes}B){quota.withinQuota ? '' : ' — OVER BUDGET'}</span>
                    <span className="flex items-center gap-1"><Clock size={9} />{isExecuting ? `${elapsed}s elapsed` : 'idle'} · cap {STUDIO_QUOTAS.maxSignals.toLocaleString()} signals</span>
                    {resources ? (
                        <span className="text-emerald-400">server resources: {Object.entries(resources).map(([k, v]) => `${k}=${v}`).join(' ')}</span>
                    ) : (
                        <span>server resources: not reported — elapsed + convention limits shown</span>
                    )}
                </div>
                <div ref={logRef} role="log" aria-live="polite" className="flex-1 overflow-auto p-2 font-mono text-[10px] leading-relaxed text-[#8b95a7] bg-black/20">
                    {logs.length === 0 ? <div className="text-[#475569]">No logs — run a strategy to see kernel state, quota, and provenance.</div> : logs.map((l, i) => <div key={i} className={l.startsWith('[error]') ? 'text-red-400' : ''}>{l}</div>)}
                </div>
            </div>
            <div className="w-[260px] flex flex-col flex-shrink-0">
                <div className="h-7 px-3 border-b border-white/5 flex items-center gap-2 bg-[#0a0a0f]">
                    <Activity size={12} className="text-blue-400" />
                    <span className="text-[10px] font-mono font-bold tracking-widest text-white">VARIABLES</span>
                </div>
                <div className="flex-1 overflow-auto p-2 space-y-1 font-mono text-[10px]">
                    {vars.map((v) => {
                        const page = paginateVariable(v.rows, varPage[v.name] || 0);
                        const isOpen = expanded === v.name;
                        return (
                            <div key={v.name} className="border border-white/5 rounded px-2 py-1 bg-white/[0.02]">
                                <button aria-label={`${isOpen ? 'Collapse' : 'Expand'} variable ${v.name}`} aria-expanded={isOpen} onClick={() => setExpanded(isOpen ? null : v.name)} className="w-full flex justify-between gap-1 text-left">
                                    <span className="text-amber-400">{isOpen ? '▾' : '▸'} {v.name}</span>
                                    <span className="text-[#64748b]">{v.type}</span>
                                    <span className="text-white truncate max-w-[80px]">{String(v.preview)}</span>
                                </button>
                                {isOpen && (
                                    <div className="mt-1 space-y-1">
                                        {page.total === 0 && <div className="text-[#475569]">empty</div>}
                                        {page.items.slice(0, 10).map((row, i) => (
                                            <div key={i} className="truncate text-[#8b95a7]">{typeof row === 'object' ? JSON.stringify(row).slice(0, 80) : String(row)}</div>
                                        ))}
                                        {page.total > 10 && <div className="text-[#475569]">showing 10 of page item preview…</div>}
                                        <div className="flex items-center justify-between text-[#64748b]">
                                            <button aria-label={`Previous page of ${v.name}`} disabled={page.page === 0} onClick={() => setVarPage((p) => ({ ...p, [v.name]: page.page - 1 }))} className="px-1 hover:text-white disabled:opacity-30">‹</button>
                                            <span>page {page.page + 1}/{page.totalPages} · {page.total} rows · {VARS_PAGE_SIZE}/page</span>
                                            <button aria-label={`Next page of ${v.name}`} disabled={page.page >= page.totalPages - 1} onClick={() => setVarPage((p) => ({ ...p, [v.name]: page.page + 1 }))} className="px-1 hover:text-white disabled:opacity-30">›</button>
                                        </div>
                                        <button aria-label={`Close variable ${v.name}`} onClick={() => { setExpanded(null); }} className="text-[#64748b] hover:text-white flex items-center gap-1"><X size={9} />close</button>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
