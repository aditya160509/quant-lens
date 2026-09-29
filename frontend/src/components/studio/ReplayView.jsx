"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Hash, Pause, Play, RotateCcw, Search } from 'lucide-react';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import { buildReplayEvents, compareReplayRuns, matchesReplayBreakpoint, positionStateAtCursor, replayEventTypes, replayFillCausality } from '@/lib/studioReplay';
import { getStudioJob } from '@/lib/studioApi';
import { normalizeStudioExecutionResult, studioComparisonCompatibility } from '@/lib/studioResults';
import { isStudioExecutionResponse } from '@/lib/studioValidators';
import VirtualTradeLedger, { tradeReturn } from './results/VirtualTradeLedger';

const formatValue = (value) => {
    if (value === null || value === undefined) return 'Unavailable';
    if (typeof value === 'number') return Number.isFinite(value) ? value.toFixed(4) : 'Unavailable';
    return String(value);
};

function StrategyReplayView() {
    const data = useStudioResultStore((state) => state.data);
    const setData = useStudioResultStore((state) => state.setData);
    const setPlayIndex = useStudioResultStore((state) => state.setPlayIndex);
    const setActiveTab = useStudioWorkspaceStore((state) => state.setActiveTab);
    const [cursor, setCursor] = useState(0);
    const [playing, setPlaying] = useState(false);
    const [speed, setSpeed] = useState(1);
    const initialLink = useMemo(() => {
        if (typeof window === 'undefined') return { run: '', event: '', timestamp: null, filter: 'all', query: '' };
        const params = new URLSearchParams(window.location.search);
        const requestedFilter = params.get('replay_filter');
        const requestedTime = params.get('time');
        return {
            run: params.get('run') || '',
            event: params.get('event') || '',
            timestamp: requestedTime !== null && Number.isFinite(Number(requestedTime)) ? Number(requestedTime) : null,
            filter: replayEventTypes.includes(requestedFilter) ? requestedFilter : 'all',
            query: params.get('replay_query') || '',
        };
    }, []);
    const [filter, setFilter] = useState(initialLink.filter);
    const [query, setQuery] = useState(initialLink.query);
    const [runInput, setRunInput] = useState(initialLink.run || data.runId || '');
    const [loadError, setLoadError] = useState(null);
    const [compareInput, setCompareInput] = useState('');
    const [comparisonRun, setComparisonRun] = useState(null);
    const [comparisonError, setComparisonError] = useState('');
    const [jobEvents, setJobEvents] = useState([]);
    const [breakpointType, setBreakpointType] = useState('none');
    const [breakpointMetric, setBreakpointMetric] = useState('none');
    const [breakpointOperator, setBreakpointOperator] = useState('<=');
    const [breakpointThreshold, setBreakpointThreshold] = useState('');
    const [breakpointHit, setBreakpointHit] = useState(null);
    const [loadingRun, setLoadingRun] = useState(Boolean(initialLink.run && initialLink.run !== data.runId));
    const events = useMemo(() => buildReplayEvents(data), [data]);
    const visibleEvents = useMemo(() => events.filter((event) => (
        (filter === 'all' || event.type === filter)
        && (!query || `${event.event_id} ${event.type} ${JSON.stringify(event.payload)}`.toLowerCase().includes(query.toLowerCase()))
    )), [events, filter, query]);
    const currentIndex = Math.min(cursor, Math.max(0, visibleEvents.length - 1));
    const selected = visibleEvents[currentIndex] || null;
    const positionState = useMemo(() => positionStateAtCursor(visibleEvents, currentIndex), [visibleEvents, currentIndex]);
    const fillCausality = useMemo(() => replayFillCausality(data), [data]);
    const positionMarkers = useMemo(() => visibleEvents.map((event, index) => ({ event, index })).filter(({ event }) => event.type === 'position_open' || event.type === 'position_close').slice(0, 60), [visibleEvents]);
    const trades = data.trades || [];
    const knownReturns = trades.map(tradeReturn).filter(Number.isFinite);
    const winCount = knownReturns.filter((value) => value > 0).length;
    const divergence = useMemo(() => comparisonRun ? compareReplayRuns(data, comparisonRun) : null, [comparisonRun, data]);

    const applyPersistedJob = (job) => {
        if (job.status !== 'completed' || !isStudioExecutionResponse(job.result)) {
            throw new Error(job.status === 'completed' ? 'Persisted job is not a valid execution artifact.' : `Run is ${job.status}, not completed.`);
        }
        const normalized = normalizeStudioExecutionResult(job.result, job.job_id);
        setData(normalized);
        const restoredEvents = buildReplayEvents(normalized);
        const linkedEvents = restoredEvents.filter((event) => (
            (initialLink.filter === 'all' || event.type === initialLink.filter)
            && (!initialLink.query || `${event.event_id} ${event.type} ${JSON.stringify(event.payload)}`.toLowerCase().includes(initialLink.query.toLowerCase()))
        ));
        const requestedIndex = linkedEvents.findIndex((event) => initialLink.event
            ? event.event_id === initialLink.event
            : initialLink.timestamp !== null && event.timestamp === initialLink.timestamp);
        setCursor(requestedIndex >= 0 ? requestedIndex : 0);
        setFilter(initialLink.filter);
        setQuery(initialLink.query);
        return normalized;
    };

    useEffect(() => {
        if (!initialLink.run || initialLink.run === data.runId) return undefined;
        const controller = new AbortController();
        getStudioJob(initialLink.run, { signal: controller.signal })
            .then((job) => { applyPersistedJob(job); setLoadError(null); })
            .catch((error) => { if (!controller.signal.aborted) setLoadError(error instanceof Error ? error.message : 'Could not load persisted run.'); })
            .finally(() => { if (!controller.signal.aborted) setLoadingRun(false); });
        return () => controller.abort();
        // Initial deep-link hydration runs once; manual loads use the explicit action below.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!playing || visibleEvents.length < 2) return undefined;
        const predicate = breakpointType === 'none' && breakpointMetric === 'none' ? null : {
            event_type: breakpointType === 'none' ? 'any' : breakpointType,
            metric: breakpointMetric,
            operator: breakpointOperator,
            threshold: Number(breakpointThreshold),
        };
        const timer = setInterval(() => {
            setCursor((current) => {
                const next = Math.min(visibleEvents.length - 1, current + 1);
                const candidate = visibleEvents[next];
                if (predicate && candidate && matchesReplayBreakpoint(candidate, predicate)) {
                    setBreakpointHit(candidate.event_id);
                    setPlaying(false);
                    return next;
                }
                if (next >= visibleEvents.length - 1) {
                    setPlaying(false);
                    return next;
                }
                return next;
            });
        }, Math.max(40, 500 / speed));
        return () => clearInterval(timer);
    }, [playing, speed, visibleEvents, breakpointType, breakpointMetric, breakpointOperator, breakpointThreshold]);

    useEffect(() => {
        if (!data.runId) {
            setJobEvents([]);
            return undefined;
        }
        const controller = new AbortController();
        getStudioJob(data.runId, { signal: controller.signal })
            .then((job) => { if (Array.isArray(job.events)) setJobEvents(job.events); })
            .catch(() => {});
        return () => controller.abort();
    }, [data.runId]);

    useEffect(() => {
        if (!selected) return;
        const barIndex = selected.payload.bar_index ?? (selected.type === 'market' ? selected.source_index : null);
        if (Number.isInteger(barIndex)) setPlayIndex(barIndex);
    }, [selected, setPlayIndex]);

    useEffect(() => {
        if (typeof window === 'undefined' || !selected || !data.runId) return;
        const params = new URLSearchParams(window.location.search);
        params.set('run', data.runId);
        params.set('event', selected.event_id);
        params.set('time', String(selected.timestamp));
        if (filter === 'all') params.delete('replay_filter'); else params.set('replay_filter', filter);
        if (query) params.set('replay_query', query); else params.delete('replay_query');
        window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}${window.location.hash}`);
    }, [data.runId, filter, query, selected]);

    const loadRun = async () => {
        const requested = runInput.trim();
        if (!requested) return;
        setLoadingRun(true);
        setLoadError(null);
        try {
            const job = await getStudioJob(requested);
            applyPersistedJob(job);
        } catch (error) {
            setLoadError(error instanceof Error ? error.message : 'Could not load persisted run.');
        } finally {
            setLoadingRun(false);
        }
    };

    const compareRun = async () => {
        const requested = compareInput.trim();
        if (!requested) return;
        setComparisonError('');
        try {
            const job = await getStudioJob(requested);
            if (job.status !== 'completed' || !isStudioExecutionResponse(job.result)) throw new Error('Comparison run is not a completed execution artifact.');
            const normalized = normalizeStudioExecutionResult(job.result, job.job_id);
            const compatibility = studioComparisonCompatibility(data, normalized);
            if (!compatibility.compatible) throw new Error(`Comparison refused: ${compatibility.reasons.join('; ')}`);
            setComparisonRun(normalized);
        } catch (error) {
            setComparisonRun(null);
            setComparisonError(error instanceof Error ? error.message : 'Comparison run unavailable.');
        }
    };

    const openTradeOnChart = (trade) => {
        const signal = data.signals.find((candidate) => candidate.date === trade.entry_date);
        const index = Number.isInteger(signal?.idx) ? signal.idx : data.signals.indexOf(signal);
        if (index >= 0) {
            setPlayIndex(index);
            setActiveTab('develop');
        }
    };

    return (
        <div className="flex flex-1 flex-col overflow-hidden bg-[#020204]">
            <div className="flex min-h-12 items-center justify-between gap-4 border-b border-white/5 bg-[#0a0a0f] px-6 py-2">
                <div className="flex items-center gap-3">
                    <Hash className="text-amber-500" size={16} />
                    <div><h2 className="text-xs font-bold uppercase tracking-[0.2em] text-white">Deterministic Run Replay</h2><p className="mt-0.5 text-[9px] font-mono text-[#64748b]">Run {data.runId || 'current'} · observed artifacts only · orders and fills unavailable</p></div>
                </div>
                <div className="flex items-center gap-2"><input aria-label="Replay run ID" value={runInput} onChange={(event) => setRunInput(event.target.value)} placeholder="Run ID" className="h-7 w-36 rounded border border-white/10 bg-[#0f0f14] px-2 text-[10px] font-mono text-white outline-none" /><button onClick={loadRun} disabled={loadingRun || !runInput.trim()} className="h-7 rounded bg-white/10 px-3 text-[10px] font-mono text-white disabled:opacity-40">{loadingRun ? 'Loading…' : 'Load run'}</button><input aria-label="Comparison run ID" value={compareInput} onChange={(event) => setCompareInput(event.target.value)} placeholder="Compare run ID" className="h-7 w-36 rounded border border-white/10 bg-[#0f0f14] px-2 text-[10px] font-mono text-white outline-none" /><button onClick={compareRun} disabled={!compareInput.trim()} className="h-7 rounded border border-amber-400/30 px-3 text-[10px] font-mono text-amber-300 disabled:opacity-40">Compare</button></div>
            </div>

            {loadError && <div role="alert" className="border-b border-red-500/20 bg-red-500/5 px-4 py-2 text-[10px] font-mono text-red-300">{loadError}</div>}
            {comparisonError && <div role="alert" className="border-b border-red-500/20 bg-red-500/5 px-4 py-2 text-[10px] font-mono text-red-300">{comparisonError}</div>}
            {divergence && <div className="border-b border-amber-400/20 bg-amber-400/5 px-4 py-2 text-[10px] font-mono text-slate-300" role="status">Compared with {comparisonRun.runId}: {divergence.identical ? 'event streams are identical' : `${divergence.differing_events} differing events; first divergence at index ${divergence.first_divergence.index} (${divergence.first_divergence.left_type || 'missing'} vs ${divergence.first_divergence.right_type || 'missing'})`}</div>}
            <div className="border-b border-white/5 bg-[#07070b] px-4 py-2 font-mono text-[10px] text-slate-300" aria-label="Position and log sync">
                <span className="uppercase text-slate-500">Position </span>
                <strong className="text-white">{positionState.position === 0 ? 'FLAT' : positionState.position > 0 ? 'LONG' : 'SHORT'}</strong>
                <span className="ml-2 text-slate-500">after {positionState.events_observed} events{positionState.entry_event_id ? ` · entry ${positionState.entry_event_id}` : ''}</span>
                <span className="ml-4 uppercase text-slate-500">Fill causality </span>
                <span className={fillCausality.fillsAvailable ? 'text-emerald-300' : 'text-slate-400'}>{fillCausality.fillsAvailable ? 'observed' : 'unavailable'}</span>
                {!fillCausality.fillsAvailable && <span className="ml-2 text-slate-500">{fillCausality.reason}</span>}
                <span className="ml-4 uppercase text-slate-500">Job log </span>
                <span className="text-slate-400">{jobEvents.length ? `${jobEvents.length} persisted events` : 'no persisted job events for this run'}</span>
            </div>
            {positionMarkers.length > 0 && (
                <div className="flex items-center gap-1 overflow-x-auto border-b border-white/5 bg-[#07070b] px-4 py-2" aria-label="Position timeline">
                    {positionMarkers.map(({ event, index }) => (
                        <button key={event.event_id} type="button" title={`${event.event_id}`} onClick={() => { setCursor(index); setPlaying(false); }} className={`h-5 min-w-5 rounded px-1 font-mono text-[9px] ${index === currentIndex ? 'bg-amber-400 text-black' : event.type === 'position_open' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                            {event.type === 'position_open' ? 'O' : 'X'}
                        </button>
                    ))}
                </div>
            )}
            <div className="flex flex-wrap items-center gap-2 border-b border-white/5 bg-[#07070b] px-4 py-2 font-mono text-[10px]">
                <span className="uppercase text-slate-500">Breakpoint</span>
                <select aria-label="Breakpoint event type" value={breakpointType} onChange={(event) => { setBreakpointType(event.target.value); setBreakpointHit(null); }} className="h-7 rounded border border-white/10 bg-[#0f0f14] px-2 text-white"><option value="none">NO TYPE</option>{replayEventTypes.map((type) => <option key={type} value={type}>{type.toUpperCase()}</option>)}</select>
                <select aria-label="Breakpoint metric" value={breakpointMetric} onChange={(event) => { setBreakpointMetric(event.target.value); setBreakpointHit(null); }} className="h-7 rounded border border-white/10 bg-[#0f0f14] px-2 text-white"><option value="none">NO METRIC</option><option value="equity">EQUITY</option><option value="net_return">NET RETURN</option></select>
                <select aria-label="Breakpoint operator" value={breakpointOperator} onChange={(event) => setBreakpointOperator(event.target.value)} className="h-7 rounded border border-white/10 bg-[#0f0f14] px-2 text-white"><option value="<=">&lt;=</option><option value=">=">&gt;=</option></select>
                <input aria-label="Breakpoint threshold" value={breakpointThreshold} onChange={(event) => { setBreakpointThreshold(event.target.value); setBreakpointHit(null); }} placeholder="threshold" inputMode="decimal" className="h-7 w-28 rounded border border-white/10 bg-[#0f0f14] px-2 text-white" />
                {breakpointHit && <span role="status" className="text-amber-300">Paused at {breakpointHit}</span>}
            </div>

            <div className="flex items-center gap-2 border-b border-white/5 bg-[#07070b] px-4 py-2">
                <button aria-label="First replay event" disabled={!visibleEvents.length} onClick={() => setCursor(0)} className="p-1.5 text-slate-400 hover:text-white disabled:opacity-30"><ChevronFirst size={15} /></button>
                <button aria-label="Previous replay event" disabled={!visibleEvents.length} onClick={() => setCursor((value) => Math.max(0, value - 1))} className="p-1.5 text-slate-400 hover:text-white disabled:opacity-30"><ChevronLeft size={15} /></button>
                <button aria-label={playing ? 'Pause replay' : 'Play replay'} disabled={!visibleEvents.length} onClick={() => setPlaying((value) => !value)} className="rounded bg-amber-400 px-3 py-1.5 text-black disabled:opacity-30">{playing ? <Pause size={14} /> : <Play size={14} />}</button>
                <button aria-label="Next replay event" disabled={!visibleEvents.length} onClick={() => setCursor((value) => Math.min(visibleEvents.length - 1, value + 1))} className="p-1.5 text-slate-400 hover:text-white disabled:opacity-30"><ChevronRight size={15} /></button>
                <button aria-label="Last replay event" disabled={!visibleEvents.length} onClick={() => setCursor(Math.max(0, visibleEvents.length - 1))} className="p-1.5 text-slate-400 hover:text-white disabled:opacity-30"><ChevronLast size={15} /></button>
                <span className="ml-2 text-[10px] font-mono text-slate-400">{visibleEvents.length ? currentIndex + 1 : 0} / {visibleEvents.length}</span>
                <select aria-label="Replay speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="ml-3 h-7 rounded border border-white/10 bg-[#0f0f14] px-2 text-[10px] font-mono text-white"><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={5}>5×</option></select>
                <select aria-label="Replay event filter" value={filter} onChange={(event) => { setFilter(event.target.value); setCursor(0); setPlaying(false); }} className="h-7 rounded border border-white/10 bg-[#0f0f14] px-2 text-[10px] font-mono text-white"><option value="all">ALL EVENTS</option>{replayEventTypes.map((type) => <option key={type} value={type}>{type.replaceAll('_', ' ').toUpperCase()}</option>)}</select>
                <label className="ml-auto flex items-center gap-2 rounded border border-white/10 bg-[#0f0f14] px-2"><Search size={12} className="text-slate-500" /><input aria-label="Search replay events" value={query} onChange={(event) => { setQuery(event.target.value); setCursor(0); setPlaying(false); }} placeholder="event or value" className="h-7 w-40 bg-transparent text-[10px] font-mono text-white outline-none" /></label>
            </div>

            <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_340px]">
                <div className="min-h-0 overflow-auto p-4">{events.length ? <VirtualTradeLedger trades={trades} onSelect={openTradeOnChart} height={460} /> : <div className="flex h-full flex-col items-center justify-center text-[#475569]"><RotateCcw size={42} className="mb-3" /><p className="text-xs font-mono uppercase tracking-widest">Execute a strategy or load a completed run ID</p></div>}</div>
                <aside className="overflow-auto border-l border-white/5 bg-[#08080d] p-4 font-mono">
                    <div className="mb-3 text-[9px] uppercase tracking-widest text-amber-400">Event inspector</div>
                    {selected ? <>
                        <div className="text-sm font-bold text-white">{selected.type.replaceAll('_', ' ')}</div>
                        <div className="mt-1 text-[10px] text-slate-500">{selected.event_id} · {new Date(selected.timestamp).toISOString()}</div>
                        <dl className="mt-4 space-y-2 text-[10px]">{Object.entries(selected.payload).map(([key, value]) => <div key={key} className="flex justify-between gap-4 border-b border-white/5 pb-2"><dt className="text-slate-500">{key}</dt><dd className="text-right text-slate-200">{formatValue(value)}</dd></div>)}</dl>
                        <div className="mt-5 text-[9px] uppercase tracking-wider text-slate-500">Causal events</div>
                        <div className="mt-2 space-y-1 text-[10px] text-slate-300">{selected.causal_event_ids.length ? selected.causal_event_ids.map((id) => <div key={id}>{id}</div>) : <div>None recorded</div>}</div>
                        <div className="mt-5 text-[9px] uppercase tracking-wider text-slate-500">Persisted job log</div>
                        <div className="mt-2 max-h-40 space-y-1 overflow-auto text-[10px] text-slate-300">{jobEvents.length ? jobEvents.slice(0, 50).map((entry) => <div key={entry.id}>{entry.id} · {entry.status} · {entry.at}</div>) : <div>No persisted job events for this run.</div>}</div>
                    </> : <div className="text-xs text-slate-500">No events match the current filter.</div>}
                </aside>
            </div>
        </div>
    );
}

function PortfolioReplay({ artifact }) {
    const events = useMemo(() => [
        { type: 'artifact', label: 'Artifact constructed', payload: { artifact_id: artifact.artifact_id, engine_version: artifact.engine_version, objective: artifact.objective } },
        { type: 'model', label: 'Models resolved', payload: artifact.model },
        { type: 'constraints', label: 'Constraints enforced', payload: { ...artifact.constraints, exposures: artifact.constraint_exposures } },
        { type: 'optimization', label: 'Target solved', payload: artifact.metrics },
        ...artifact.assets.map((asset) => ({ type: 'trade', label: `${asset} target`, payload: { asset, current_weight: artifact.current_weights[asset], target_weight: artifact.weights[asset], trade_weight: artifact.trades[asset], risk_contribution: artifact.risk_contribution[asset] } })),
        ...(artifact.scenario_results || []).map((scenario) => ({ type: 'scenario', label: scenario.name, payload: scenario })),
    ], [artifact]);
    const [cursor, setCursor] = useState(0);
    const selected = events[cursor];
    return <div className="flex flex-1 flex-col overflow-hidden bg-[#020204]"><header className="flex min-h-12 items-center justify-between border-b border-white/10 px-6"><div><h2 className="text-xs font-bold uppercase tracking-[0.2em] text-white">Portfolio artifact replay</h2><p className="mt-1 font-mono text-[9px] text-slate-500">{artifact.artifact_id} · deterministic construction sequence</p></div><span className="font-mono text-[9px] text-slate-600">{cursor + 1} / {events.length}</span></header><div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_360px]"><div className="overflow-auto p-6"><div className="border-y border-white/10">{events.map((event, index) => <button key={`${event.type}-${index}`} type="button" onClick={() => setCursor(index)} className={`grid w-full grid-cols-[44px_120px_1fr] border-b border-white/5 px-3 py-3 text-left font-mono text-[10px] ${cursor === index ? 'bg-amber-400/[0.07] text-white' : 'text-slate-500 hover:bg-white/[0.02]'}`}><span>{String(index + 1).padStart(2, '0')}</span><span className="uppercase text-amber-300">{event.type}</span><span>{event.label}</span></button>)}</div></div><aside className="overflow-auto border-l border-white/10 bg-[#08080d] p-5"><div className="text-[9px] uppercase tracking-wider text-amber-400">Event inspector</div><h3 className="mt-2 text-sm font-semibold text-white">{selected.label}</h3><dl className="mt-5 space-y-2 font-mono text-[10px]">{Object.entries(selected.payload || {}).map(([key, value]) => <div key={key} className="border-b border-white/5 pb-2"><dt className="mb-1 text-slate-600">{key}</dt><dd className="break-words text-slate-300">{typeof value === 'object' ? JSON.stringify(value) : formatValue(value)}</dd></div>)}</dl></aside></div></div>;
}

export default function ReplayView() {
    const data = useStudioResultStore((state) => state.data);
    const portfolioArtifact = useStudioResultStore((state) => state.portfolioArtifact);
    return portfolioArtifact && !data.runId ? <PortfolioReplay artifact={portfolioArtifact} /> : <StrategyReplayView />;
}
