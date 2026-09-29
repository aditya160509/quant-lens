"use client";
import React, { useEffect, useRef, useState } from 'react';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioEditorStore } from '@/stores/studio/editorStore';
import { useStudioAnalysis } from '@/hooks/studio/useStudioAnalysis';
import { Shield, Activity, TrendingDown, Check } from 'lucide-react';
import { getPromotionAudit, recordPromotionAudit, runSensitivityGrid, runValidationScenarios } from '@/lib/studioApi';

const Metric = ({ label, value, trend, size = 'default' }) => (
    <div className={`bg-[#0f0f14] border border-white/5 rounded-lg ${size === 'large' ? 'p-4' : 'p-3'}`}>
        <div className="text-[10px] font-mono text-[#64748b] uppercase mb-1">{label}</div>
        <div className={`font-mono font-bold ${
            size === 'large' ? 'text-xl' : 'text-lg'
        } ${
            trend === 'up' ? 'text-[#10b981]' : 
            trend === 'down' ? 'text-[#ef4444]' : 
            'text-white'
        }`}>
            {value ?? '--'}
        </div>
    </div>
);

const formatMetric = (value, suffix = '', decimals = 1) => (
    Number.isFinite(value) ? `${value.toFixed(decimals)}${suffix}` : '--'
);

const SensitivityHeatmap = ({ lookbacks, thresholds, cells }) => {
    const canvasRef = useRef(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !cells?.length) return;
        const sharpes = cells.map((cell) => cell.sharpe).filter(Number.isFinite);
        const min = sharpes.length ? Math.min(...sharpes) : 0;
        const max = sharpes.length ? Math.max(...sharpes) : 1;
        const span = max - min || 1;
        const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
        const cellW = 72;
        const cellH = 36;
        canvas.width = thresholds.length * cellW * dpr;
        canvas.height = lookbacks.length * cellH * dpr;
        canvas.style.width = `${thresholds.length * cellW}px`;
        canvas.style.height = `${lookbacks.length * cellH}px`;
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        ctx.fillStyle = '#0a0a0f';
        ctx.fillRect(0, 0, thresholds.length * cellW, lookbacks.length * cellH);
        cells.forEach((cell) => {
            const row = lookbacks.indexOf(cell.lookback);
            const col = thresholds.indexOf(cell.threshold);
            if (row < 0 || col < 0) return;
            const normalized = Number.isFinite(cell.sharpe) ? (cell.sharpe - min) / span : 0;
            ctx.fillStyle = Number.isFinite(cell.sharpe)
                ? `rgba(${Math.round(239 - normalized * 205)},${Math.round(68 + normalized * 129)},${Math.round(68 + normalized * 52)},0.85)`
                : 'rgba(255,255,255,0.06)';
            ctx.fillRect(col * cellW + 1, row * cellH + 1, cellW - 2, cellH - 2);
            ctx.fillStyle = '#fff';
            ctx.font = '10px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.fillText(Number.isFinite(cell.sharpe) ? cell.sharpe.toFixed(2) : '--', col * cellW + cellW / 2, row * cellH + cellH / 2 + 3);
        });
    }, [cells, lookbacks, thresholds]);
    return <canvas ref={canvasRef} role="img" aria-label="Parameter sensitivity heatmap on Canvas2D" className="rounded border border-white/10" />;
};

const SensitivityPanel = ({ closes }) => {
    const [lookbackText, setLookbackText] = useState('10,20,40');
    const [thresholdText, setThresholdText] = useState('0.01,0.02,0.05');
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const run = async () => {
        setError('');
        setResult(null);
        const lookbacks = lookbackText.split(',').map((item) => Number(item.trim())).filter(Number.isInteger);
        const thresholds = thresholdText.split(',').map((item) => Number(item.trim())).filter(Number.isFinite);
        if (!lookbacks.length || !thresholds.length || lookbacks.length * thresholds.length > 100) {
            setError('Provide 1-10 lookbacks and 1-10 thresholds within the 100-cell budget.');
            return;
        }
        if (!closes || closes.length < 30) {
            setError('Sensitivity unavailable: at least 30 observed closes are required.');
            return;
        }
        setLoading(true);
        try {
            const payload = await runSensitivityGrid({ closes: closes.slice(-1000), lookbacks, thresholds });
            setResult(payload);
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Sensitivity grid failed.');
        } finally {
            setLoading(false);
        }
    };
    return (
        <section aria-label="Parameter sensitivity surface" className="rounded-xl border border-white/10 bg-[#0f0f14] p-4">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-amber-400">Parameter sensitivity surface</div>
            <p className="mt-1 text-[9px] font-mono text-slate-500">Deterministic Sharpe per lookback and threshold cell via the canonical metrics engine. Table plus Canvas2D heatmap; no 3D rendering.</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-2 text-[9px] font-mono text-slate-400">Lookbacks<input aria-label="Sensitivity lookbacks" value={lookbackText} onChange={(event) => setLookbackText(event.target.value)} className="h-7 w-36 border border-white/10 bg-black/20 px-2 text-[10px] text-white" /></label>
                <label className="flex items-center gap-2 text-[9px] font-mono text-slate-400">Thresholds<input aria-label="Sensitivity thresholds" value={thresholdText} onChange={(event) => setThresholdText(event.target.value)} className="h-7 w-44 border border-white/10 bg-black/20 px-2 text-[10px] text-white" /></label>
                <button type="button" onClick={run} disabled={loading} className="h-7 border border-amber-400/40 px-3 text-[10px] font-bold uppercase text-amber-300 disabled:opacity-40">{loading ? 'Running…' : 'Run grid'}</button>
            </div>
            {error && <div role="alert" className="mt-2 text-[10px] font-mono text-red-300">{error}</div>}
            {result && (
                <div className="mt-3 space-y-3">
                    <div className="overflow-auto"><table className="w-full text-[10px] font-mono"><thead><tr className="text-left text-slate-500"><th className="py-1 pr-3">Lookback \ Threshold</th>{result.thresholds.map((threshold) => <th key={threshold} className="py-1 pr-3">{threshold}</th>)}</tr></thead><tbody>{result.lookbacks.map((lookback) => <tr key={lookback} className="border-t border-white/5 text-slate-200"><td className="py-1 pr-3 text-amber-300">{lookback}</td>{result.thresholds.map((threshold) => { const cell = result.cells.find((candidate) => candidate.lookback === lookback && candidate.threshold === threshold); return <td key={threshold} className="py-1 pr-3">{Number.isFinite(cell?.sharpe) ? cell.sharpe.toFixed(2) : 'Unavailable'}</td>; })}</tr>)}</tbody></table></div>
                    <SensitivityHeatmap lookbacks={result.lookbacks} thresholds={result.thresholds} cells={result.cells} />
                    <div className="text-[9px] font-mono text-slate-600">Methodology: {result.methodology}.</div>
                </div>
            )}
        </section>
    );
};

const ScenarioPanel = ({ returns }) => {
    const [costShockBps, setCostShockBps] = useState(10);
    const [missingPct, setMissingPct] = useState(5);
    const [delayBars, setDelayBars] = useState(1);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const run = async () => {
        setError('');
        setResult(null);
        if (!returns || returns.length < 100) {
            setError('Scenario evidence unavailable: at least 100 observed returns are required.');
            return;
        }
        setLoading(true);
        try {
            const payload = await runValidationScenarios({ returns: returns.slice(-2000), nFolds: 3, oosDays: 20, costShockBps: costShockBps, missingPct, delayBars });
            setResult(payload);
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Scenario evidence failed.');
        } finally {
            setLoading(false);
        }
    };
    return (
        <section aria-label="Scenario evidence" className="rounded-xl border border-white/10 bg-[#0f0f14] p-4">
            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-amber-400">Scenario evidence</div>
            <p className="mt-1 text-[9px] font-mono text-slate-500">Cost shock, missing-data, and delay scenarios reuse the walk-forward engine. Liquidity, regime, and adversarial tests report as skipped when governed inputs are absent.</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-2 text-[9px] font-mono text-slate-400">Cost shock (bps)<input aria-label="Cost shock bps" type="number" min="0" max="1000" value={costShockBps} onChange={(event) => setCostShockBps(Number(event.target.value))} className="h-7 w-20 border border-white/10 bg-black/20 px-2 text-[10px] text-white" /></label>
                <label className="flex items-center gap-2 text-[9px] font-mono text-slate-400">Missing (%)<input aria-label="Missing data percent" type="number" min="0" max="50" value={missingPct} onChange={(event) => setMissingPct(Number(event.target.value))} className="h-7 w-20 border border-white/10 bg-black/20 px-2 text-[10px] text-white" /></label>
                <label className="flex items-center gap-2 text-[9px] font-mono text-slate-400">Delay (bars)<input aria-label="Delay bars" type="number" min="1" max="5" value={delayBars} onChange={(event) => setDelayBars(Number(event.target.value))} className="h-7 w-20 border border-white/10 bg-black/20 px-2 text-[10px] text-white" /></label>
                <button type="button" onClick={run} disabled={loading} className="h-7 border border-amber-400/40 px-3 text-[10px] font-bold uppercase text-amber-300 disabled:opacity-40">{loading ? 'Running…' : 'Run scenarios'}</button>
            </div>
            {error && <div role="alert" className="mt-2 text-[10px] font-mono text-red-300">{error}</div>}
            {result && (
                <div className="mt-3 space-y-2">
                    {(result.scenarios || []).map((scenario) => <div key={scenario.id} className="flex items-center justify-between gap-4 border-t border-white/5 pt-2 font-mono text-[10px]"><span className="uppercase text-slate-300">{scenario.id.replaceAll('_', ' ')}</span><span className="text-slate-400">{scenario.status === 'observed' ? `OOS Sharpe ${Number.isFinite(scenario.avg_oos_sharpe) ? scenario.avg_oos_sharpe.toFixed(2) : 'Unavailable'} · consistency ${scenario.consistency ?? 'Unavailable'}%` : scenario.reason || 'Unavailable'}</span></div>)}
                    <div className="pt-2 text-[9px] font-mono uppercase tracking-wider text-slate-500">Skipped tests</div>
                    {(result.skipped || []).map((item) => <div key={item.id} className="font-mono text-[10px] text-slate-500"><span className="uppercase text-slate-400">{item.id}</span> · skipped · {item.reason}</div>)}
                </div>
            )}
        </section>
    );
};
const FoldCard = ({ fold, index }) => {
    const hasOosSharpe = Number.isFinite(fold.oosSharpe);
    const passed = hasOosSharpe && fold.oosSharpe > 0.5;

    return (
    <div className="p-4 bg-[#0f0f14] border border-white/5 rounded-xl">
        <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono font-bold text-amber-500 uppercase">Fold {index + 1}</span>
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-[8px] font-mono font-bold uppercase ${
                passed
                ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' 
                : hasOosSharpe
                ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                : 'bg-white/5 text-[#64748b] border border-white/10'
            }`}>
                {passed ? 'PASS' : hasOosSharpe ? 'FAIL' : 'UNAVAILABLE'}
            </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
            <div>
                <div className="text-[9px] font-mono text-[#64748b] mb-0.5">IS Sharpe</div>
                <div className="text-sm font-mono font-bold text-white">{formatMetric(fold.isSharpe, '', 2)}</div>
            </div>
            <div>
                <div className="text-[9px] font-mono text-[#64748b] mb-0.5">OOS Sharpe</div>
                <div className={`text-sm font-mono font-bold ${!hasOosSharpe ? 'text-[#64748b]' : fold.oosSharpe > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatMetric(fold.oosSharpe, '', 2)}
                </div>
            </div>
        </div>
        <div className="mt-3 border-t border-white/5 pt-2 text-[9px] font-mono leading-relaxed text-slate-400">
            Train [{fold.trainStart}, {fold.trainEnd})<br />
            Gap {fold.purgeDays + fold.embargoDays} bars · Test [{fold.testStart}, {fold.testEnd})
        </div>
    </div>
    );
};

const ValidateView = () => {
    const data = useStudioResultStore((s) => s.data);
    const wfLoading = useStudioResultStore((s) => s.wfLoading);
    const wfError = useStudioResultStore((s) => s.wfError);
    const wfJob = useStudioResultStore((s) => s.wfJob);
    const codeA = useStudioEditorStore((s) => s.codeA);
    const portfolioArtifact = useStudioResultStore((s) => s.portfolioArtifact);
    const setPromotionAuditRecords = useStudioResultStore((s) => s.setPromotionAuditRecords);
    const { runWalkForward, cancelWalkForward } = useStudioAnalysis();
    const [folds, setFolds] = useState(5);
    const [purgeDays, setPurgeDays] = useState(2);
    const [embargoDays, setEmbargoDays] = useState(1);
    const [minOosSharpe, setMinOosSharpe] = useState(0.5);
    const [minConsistencyPct, setMinConsistencyPct] = useState(50);
    const [auditActor, setAuditActor] = useState('');
    const [auditRationale, setAuditRationale] = useState('');
    const [auditRecords, setAuditRecords] = useState([]);
    const [auditError, setAuditError] = useState('');
    const [validationSource, setValidationSource] = useState('strategy');
    const wf = data.wfData;
    const portfolioReturns = portfolioArtifact?.observed_portfolio_returns;
    const strategyReady = Boolean(codeA && data.equityCurve.length >= 100);
    const portfolioReady = Array.isArray(portfolioReturns) && portfolioReturns.length >= 100;
    const resolvedValidationSource = validationSource === 'strategy' && !strategyReady && portfolioArtifact ? 'portfolio' : validationSource;
    const sourceReady = resolvedValidationSource === 'portfolio' ? portfolioReady : strategyReady;

    const handleRun = () => {
        setAuditRecords([]);
        setAuditError('');
        runWalkForward(
            folds,
            purgeDays,
            embargoDays,
            minOosSharpe,
            minConsistencyPct,
            resolvedValidationSource === 'portfolio' ? portfolioReturns : null,
            resolvedValidationSource === 'portfolio' ? portfolioArtifact?.artifact_id : data.runId,
        );
    };

    const foldData = wf?.folds ?? [];
    useEffect(() => {
        if (!wfJob?.job_id || wfJob.status !== 'completed') return;
        const controller = new AbortController();
        getPromotionAudit(wfJob.job_id, { signal: controller.signal }).then((payload) => { const records = payload.records || []; setAuditRecords(records); setPromotionAuditRecords(records); }).catch((cause) => { if (cause?.code !== 'STUDIO_CANCELLED') setAuditError(cause?.message || 'Audit history unavailable.'); });
        return () => controller.abort();
    }, [setPromotionAuditRecords, wfJob?.job_id, wfJob?.status]);
    const recordDecision = async (action) => {
        if (!auditActor.trim() || !auditRationale.trim()) { setAuditError('Actor and rationale are required.'); return; }
        setAuditError('');
        try {
            const payload = await recordPromotionAudit(wfJob.job_id, { action, actor: auditActor.trim(), rationale: auditRationale.trim() });
            const records = [...auditRecords, payload.audit];
            setAuditRecords(records);
            setPromotionAuditRecords(records);
            setAuditRationale('');
        } catch (cause) { setAuditError(cause?.message || 'Decision could not be recorded.'); }
    };

    return (
        <div className="flex-1 flex flex-col bg-[#020204] overflow-hidden">
            {/* Header */}
            <div className="h-12 px-6 border-b border-white/5 flex items-center justify-between bg-[#0a0a0f]">
                <div className="flex items-center gap-3">
                    <Shield className="text-amber-500" size={16} />
                    <h2 className="text-xs font-bold text-white tracking-[0.2em] uppercase">Walk-Forward Validation</h2>
                </div>
                
                <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 text-[9px] font-mono text-[#64748b] uppercase">Source<select aria-label="Validation source" value={resolvedValidationSource} onChange={(event) => setValidationSource(event.target.value)} className="h-8 border border-white/10 bg-[#0f0f14] px-2 text-white"><option value="strategy">Strategy run</option>{portfolioArtifact ? <option value="portfolio">Portfolio artifact</option> : null}</select></label>
                    <label className="flex items-center gap-2 text-[9px] font-mono text-[#64748b] uppercase">
                        Purge
                        <input aria-label="Purge bars" type="number" min="0" max="252" value={purgeDays} onChange={e => setPurgeDays(Number(e.target.value))} className="w-16 bg-[#0f0f14] border border-white/10 rounded px-2 h-8 text-[11px] text-white" />
                    </label>
                    <label className="flex items-center gap-2 text-[9px] font-mono text-[#64748b] uppercase">
                        Embargo
                        <input aria-label="Embargo bars" type="number" min="0" max="252" value={embargoDays} onChange={e => setEmbargoDays(Number(e.target.value))} className="w-16 bg-[#0f0f14] border border-white/10 rounded px-2 h-8 text-[11px] text-white" />
                    </label>
                    <div className="flex items-center gap-2">
                        <span className="text-[9px] font-mono text-[#64748b] uppercase">Folds:</span>
                        <select 
                            value={folds} 
                            onChange={e => setFolds(Number(e.target.value))}
                            className="bg-[#0f0f14] border border-white/10 rounded px-3 h-8 text-[11px] font-mono text-white outline-none focus:border-amber-500/30"
                        >
                            <option value={3}>3 FOLDS</option>
                            <option value={5}>5 FOLDS</option>
                            <option value={10}>10 FOLDS</option>
                        </select>
                    </div>
                    
                    <button 
                        onClick={wfLoading ? cancelWalkForward : handleRun}
                        disabled={!wfLoading && !sourceReady}
                        className={`px-6 h-8 text-[11px] font-bold rounded-md transition-all uppercase tracking-widest disabled:opacity-50 ${wfLoading ? 'bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/25' : 'bg-amber-500 text-black hover:bg-amber-400'}`}
                    >
                        {wfLoading ? 'Cancel Validation' : 'Run Validation'}
                    </button>
                </div>
            </div>

            <div className="flex-1 flex min-h-0 overflow-hidden">
                {/* Main Content */}
                <div className="flex-1 p-6 overflow-y-auto space-y-6">
                    {resolvedValidationSource === 'portfolio' ? <div className="border-l-2 border-amber-400/60 pl-3 font-mono text-[10px] text-slate-400"><span className="text-amber-300">Portfolio {portfolioArtifact?.artifact_id || 'unavailable'}</span>{portfolioReady ? ` · ${portfolioReturns.length} observed fixed-weight returns. This tests return stability; it does not refit portfolio weights in each fold.` : ' · Validation unavailable: import at least 100 aligned return observations and optimize the portfolio.'}</div> : null}
                    <div className="flex flex-wrap items-center gap-4 border-b border-white/5 pb-4 text-[10px] font-mono uppercase text-slate-400">
                        <span className="text-amber-400">Promotion rule</span>
                        <label className="flex items-center gap-2">
                            Minimum OOS Sharpe
                            <input aria-label="Minimum OOS Sharpe" type="number" min="-5" max="5" step="0.1" value={minOosSharpe} onChange={e => setMinOosSharpe(Number(e.target.value))} className="w-16 bg-[#0f0f14] border border-white/10 rounded px-2 h-7 text-white" />
                        </label>
                        <label className="flex items-center gap-2">
                            Profitable folds
                            <input aria-label="Minimum profitable fold percentage" type="number" min="0" max="100" step="5" value={minConsistencyPct} onChange={e => setMinConsistencyPct(Number(e.target.value))} className="w-16 bg-[#0f0f14] border border-white/10 rounded px-2 h-7 text-white" />%
                        </label>
                        <span className="normal-case text-slate-500">Both checks must pass. This is a rule-based verdict, not statistical confidence.</span>
                    </div>
                    {wfError && (
                        <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-xs font-mono text-red-300">
                            {wfError}
                        </div>
                    )}
                    {wfJob?.estimate && (
                        <div className="rounded-lg border border-white/10 bg-[#0f0f14] px-4 py-3 text-[10px] font-mono text-slate-300">
                            Compute estimate: {wfJob.estimate.size} · {wfJob.estimate.work_units.toLocaleString()} units · {wfJob.estimate.budget_utilization_pct}% of enforced limit
                            <span className="ml-3 text-slate-500">{wfJob.estimate.basis}</span>
                        </div>
                    )}
                    {wfJob?.status && <div role="status" className="border-l-2 border-amber-400/60 pl-3 text-[10px] font-mono text-slate-300">Job {wfJob.job_id} · {wfJob.status}{Number.isFinite(wfJob.progress) ? ` · ${wfJob.progress}%` : ''}</div>}
                    {wf ? (
                        <>
                            {/* Summary Metrics */}
                            <div className="grid grid-cols-4 gap-4">
                                <Metric 
                                    label="IS Sharpe (Avg)" 
                                    value={formatMetric(wf.summary?.avgIsSharpe, '', 2)}
                                    size="large"
                                />
                                <Metric 
                                    label="OOS Sharpe (Avg)" 
                                    value={formatMetric(wf.summary?.avgOosSharpe, '', 2)}
                                    trend={Number.isFinite(wf.summary?.avgOosSharpe) && wf.summary.avgOosSharpe > 0.5 ? 'up' : undefined}
                                    size="large"
                                />
                                <Metric 
                                    label="Consistency" 
                                    value={formatMetric(wf.summary?.consistency, '%')}
                                    trend={Number.isFinite(wf.summary?.consistency) ? (wf.summary.consistency > 50 ? 'up' : 'down') : undefined}
                                    size="large"
                                />
                                <Metric 
                                    label="Alpha Decay" 
                                    value={formatMetric(wf.summary?.alphaDecay, '%')}
                                    trend={Number.isFinite(wf.summary?.alphaDecay) ? (wf.summary.alphaDecay < 30 ? 'up' : 'down') : undefined}
                                    size="large"
                                />
                            </div>

                            {/* Validation verdict */}
                            {wf.verdict && (
                                <div className={`p-6 rounded-xl border ${
                                    wf.verdict.status === 'PASSED' ? 'bg-emerald-500/5 border-emerald-500/20' : 
                                    wf.verdict.status === 'FAILED' ? 'bg-red-500/5 border-red-500/20' :
                                    'bg-white/[0.02] border-white/10'
                                }`}>
                                    <div className="flex justify-between items-center mb-4">
                                        <div className="flex items-center gap-3">
                                            <div className={`w-4 h-4 rounded-full flex items-center justify-center ${
                                                wf.verdict.status === 'PASSED' ? 'bg-emerald-500' :
                                                wf.verdict.status === 'FAILED' ? 'bg-red-500' : 'bg-slate-500'
                                            }`}>
                                                {wf.verdict.status === 'PASSED' ? <Check size={10} className="text-white" /> :
                                                 wf.verdict.status === 'FAILED' ? <TrendingDown size={10} className="text-white" /> :
                                                 <Activity size={10} className="text-white" />}
                                            </div>
                                            <h3 className="text-sm font-bold text-white tracking-widest uppercase">
                                                Validation verdict: {wf.verdict.status}
                                            </h3>
                                        </div>
                                        <div className="text-[11px] font-mono text-[#64748b]">RULE-BASED · NOT STATISTICAL CONFIDENCE</div>
                                    </div>
                                    <div className="space-y-2 font-mono text-[11px]">
                                        {wf.verdict.tests.map((test) => (
                                            <div key={test.id} className="flex items-center justify-between gap-4 border-t border-white/5 pt-2">
                                                <span className="text-slate-300">{test.label}</span>
                                                <span className={test.status === 'pass' ? 'text-emerald-400' : test.status === 'fail' ? 'text-red-400' : 'text-slate-500'}>
                                                    {test.status.toUpperCase()} · {Number.isFinite(test.value) ? test.value.toFixed(2) : 'Unavailable'} {test.operator} {test.threshold.toFixed(2)}{test.unit === 'percent' ? '%' : ''}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {wf.verdict && wfJob?.status === 'completed' && <section className="border border-white/10 bg-[#0f0f14] p-4" aria-label="Promotion audit">
                                <div className="mb-3 text-[10px] font-mono font-bold uppercase tracking-widest text-amber-400">Immutable promotion audit</div>
                                <div className="grid grid-cols-[180px_1fr_auto] gap-2"><input aria-label="Decision actor" value={auditActor} onChange={(event) => setAuditActor(event.target.value)} placeholder="Actor" maxLength={200} className="border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-white" /><input aria-label="Decision rationale" value={auditRationale} onChange={(event) => setAuditRationale(event.target.value)} placeholder="Required rationale" maxLength={4000} className="border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-white" /><div className="flex gap-1">{['promote', 'reject', 'override'].map((action) => <button key={action} type="button" onClick={() => recordDecision(action)} className="border border-white/10 px-2 text-[9px] font-bold uppercase text-slate-300 hover:border-amber-400/50 hover:text-white">{action}</button>)}</div></div>
                                {auditError ? <div role="alert" className="mt-2 text-[10px] text-red-300">{auditError}</div> : null}
                                <div className="mt-3 space-y-2">{auditRecords.map((record) => <div key={record.audit_id} className="border-l-2 border-white/10 pl-3 text-[9px] font-mono text-slate-400"><span className="font-bold uppercase text-slate-200">{record.action}</span> by {record.actor} · {record.created_at}<div>{record.rationale}</div><div className="text-slate-600">hash {record.record_hash?.slice(0, 16)} · thresholds frozen</div></div>)}</div>
                            </section>}

                            {/* Fold Results */}
                            <div>
                                <h3 className="text-[10px] font-mono font-bold text-amber-500 uppercase tracking-widest mb-3">
                                    Individual Fold Results
                                </h3>
                                <div className="grid grid-cols-5 gap-3">
                                    {foldData.map((fold, i) => (
                                        <FoldCard key={i} fold={fold} index={i} />
                                    ))}
                                </div>
                                {foldData.length === 0 && (
                                    <p className="text-xs font-mono text-[#64748b]">Fold-level results are unavailable.</p>
                                )}
                            </div>
                            <SensitivityPanel closes={(data.candles || []).map((candle) => candle.close).filter(Number.isFinite)} />
                            <ScenarioPanel returns={(data.equityCurve || []).slice(1).map((value, index) => (data.equityCurve[index] > 0 ? value / data.equityCurve[index] - 1 : Number.NaN)).filter(Number.isFinite)} />
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center opacity-20 py-20">
                            <Shield size={60} className="mb-4" />
                            <p className="font-mono text-sm tracking-widest uppercase">Execute a strategy first, then run validation</p>
                            <p className="font-mono text-xs text-[#64748b] mt-2">Walk-forward analysis validates OOS performance</p>
                        </div>
                    )}
                    {!wf && (
                        <div className="space-y-6">
                            <SensitivityPanel closes={(data.candles || []).map((candle) => candle.close).filter(Number.isFinite)} />
                            <ScenarioPanel returns={(data.equityCurve || []).slice(1).map((value, index) => (data.equityCurve[index] > 0 ? value / data.equityCurve[index] - 1 : Number.NaN)).filter(Number.isFinite)} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ValidateView;
