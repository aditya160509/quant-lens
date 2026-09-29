"use client";
import React, { useState, useEffect } from 'react';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioAnalysis } from '@/hooks/studio/useStudioAnalysis';
import { Activity, Shield } from 'lucide-react';
import MonteCarloCanvas from './MonteCarloCanvas';

const Metric = ({ label, value, trend }) => (
    <div className="bg-gradient-to-b from-[#121826] to-[#0d121c] border border-slate-500/25 p-3 rounded-lg shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        <div className="text-[10px] font-mono text-slate-300 uppercase mb-1 tracking-wider">{label}</div>
        <div className={`text-lg font-mono font-bold ${trend === 'up' ? 'text-[#10b981]' : trend === 'down' ? 'text-[#ef4444]' : 'text-white'}`}>
            {value ?? '--'}
        </div>
    </div>
);

const formatMultiple = (value, decimals = 2) => Number.isFinite(value) ? `${value.toFixed(decimals)}x` : '--';

const StressView = () => {
    const data = useStudioResultStore((s) => s.data);
    const mcLoading = useStudioResultStore((s) => s.mcLoading);
    const mcError = useStudioResultStore((s) => s.mcError);
    const mcJob = useStudioResultStore((s) => s.mcJob);
    const portfolioArtifact = useStudioResultStore((s) => s.portfolioArtifact);
    const { runMonteCarlo, cancelMonteCarlo } = useStudioAnalysis();
    const [simCount, setSimCount] = useState(10000);
    const [method, setMethod] = useState('moving_block_bootstrap');
    const [blockSize, setBlockSize] = useState(5);
    const [animIdx, setAnimIdx] = useState(0);
    const [analysisSource, setAnalysisSource] = useState('strategy');
    const mc = data.mcData;
    const portfolioReturns = portfolioArtifact?.observed_portfolio_returns;
    const portfolioReady = Array.isArray(portfolioReturns) && portfolioReturns.length >= 20;
    const strategyReady = data.equityCurve.length >= 20;
    const resolvedAnalysisSource = analysisSource === 'strategy' && !strategyReady && portfolioArtifact ? 'portfolio' : analysisSource;
    const sourceReady = resolvedAnalysisSource === 'portfolio' ? portfolioReady : strategyReady;

    useEffect(() => {
        if (mc && animIdx < 252) {
            const t = setTimeout(() => setAnimIdx(i => i + 2), 20);
            return () => clearTimeout(t);
        }
    }, [mc, animIdx]);

    const handleRun = () => {
        setAnimIdx(0);
        runMonteCarlo(simCount, method, blockSize, resolvedAnalysisSource === 'portfolio' ? portfolioReturns : null, resolvedAnalysisSource === 'portfolio' ? portfolioArtifact?.artifact_id : data.runId);
    };

    return (
        <div className="flex-1 flex flex-col bg-[#050812]">
            <div className="h-12 px-6 border-b border-slate-500/20 flex items-center justify-between bg-[#0c1220]">
                <div className="flex items-center gap-3">
                    <Activity className="text-amber-500" size={16} />
                    <h2 className="text-xs font-bold text-white tracking-[0.2em] uppercase">Monte Carlo Stress Engine</h2>
                </div>
                
                <div className="flex items-center gap-4">
                    <select aria-label="Stress source" value={resolvedAnalysisSource} onChange={(event) => setAnalysisSource(event.target.value)} className="bg-[#121826] border border-slate-500/30 px-3 h-8 text-[11px] font-mono text-white"><option value="strategy">STRATEGY RUN</option>{portfolioArtifact ? <option value="portfolio">PORTFOLIO ARTIFACT</option> : null}</select>
                    <select value={method} onChange={e => setMethod(e.target.value)} aria-label="Resampling method" className="bg-[#121826] border border-slate-500/30 rounded px-3 h-8 text-[11px] font-mono text-white outline-none focus:border-amber-400/60">
                        <option value="moving_block_bootstrap">MOVING BLOCK</option>
                        <option value="historical_bootstrap">HISTORICAL IID</option>
                        <option value="gaussian">GAUSSIAN</option>
                    </select>
                    {method === 'moving_block_bootstrap' && <input aria-label="Bootstrap block size" type="number" min="2" max="252" value={blockSize} onChange={e => setBlockSize(Number(e.target.value))} className="w-20 bg-[#121826] border border-slate-500/30 rounded px-2 h-8 text-[11px] font-mono text-white" />}
                    <select 
                        value={simCount} 
                        onChange={e => setSimCount(Number(e.target.value))}
                        className="bg-[#121826] border border-slate-500/30 rounded px-3 h-8 text-[11px] font-mono text-white outline-none focus:border-amber-400/60"
                    >
                        <option value={1000}>1,000 PATHS</option>
                        <option value={5000}>5,000 PATHS</option>
                        <option value={10000}>10,000 PATHS</option>
                    </select>
                    
                    <button 
                        onClick={mcLoading ? cancelMonteCarlo : handleRun}
                        disabled={!mcLoading && !sourceReady}
                        className={`px-6 h-8 text-[11px] font-bold rounded-md transition-all uppercase tracking-widest disabled:opacity-50 ${mcLoading ? 'bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/25' : 'bg-amber-400 text-black hover:bg-amber-300 shadow-[0_0_18px_rgba(251,191,36,0.35)]'}`}
                    >
                        {mcLoading ? 'Cancel Simulation' : 'Run Simulation'}
                    </button>
                </div>
            </div>

            <div className="flex-1 flex min-h-0">
                <div className="flex-1 p-6 relative bg-[#050812]">
                    {resolvedAnalysisSource === 'portfolio' && !portfolioReady ? <div className="absolute left-6 right-6 top-6 z-10 border-l-2 border-amber-400/60 pl-3 text-[10px] font-mono text-slate-400">Portfolio stress requires at least 20 imported return observations. No return series is inferred from assumptions.</div> : null}
                    {mcError && (
                        <div role="alert" className="absolute left-6 right-6 top-6 z-10 rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-xs font-mono text-red-200">
                            {mcError}
                        </div>
                    )}
                    {mc ? (
                        <MonteCarloCanvas data={mc} animIdx={animIdx} />
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center opacity-10">
                            <Activity size={80} className="mb-4" />
                            <p className="font-mono text-sm tracking-[0.3em] text-slate-300">INITIALIZE PATH ENGINE</p>
                        </div>
                    )}
                </div>

                <div className="w-[280px] border-l border-slate-500/20 p-4 space-y-4 bg-[#0d1321]/85 overflow-y-auto">
                    <div className="text-[10px] font-mono font-bold text-amber-300 tracking-widest uppercase mb-2">Simulation Summary</div>
                    {mcJob?.estimate && (
                        <div className="rounded-lg border border-slate-500/20 bg-[#121826] px-3 py-2 text-[10px] font-mono text-slate-300">
                            Compute: {mcJob.estimate.size} · {mcJob.estimate.work_units.toLocaleString()} units · {mcJob.estimate.budget_utilization_pct}% of limit
                            <div className="mt-1 text-slate-500">{mcJob.estimate.basis}</div>
                        </div>
                    )}
                    {mcJob?.status && <div role="status" className="border-l-2 border-amber-400/60 pl-3 text-[10px] font-mono text-slate-300">Job {mcJob.job_id} · {mcJob.status}{Number.isFinite(mcJob.progress) ? ` · ${mcJob.progress}%` : ''}</div>}
                    
                    <Metric label="Risk of Ruin" value={mc ? `${mc.summary.riskOfRuin}%` : '--'} trend={mc?.summary.riskOfRuin > 10 ? 'down' : 'up'} />
                    <Metric label="Prob. Positive" value={mc ? `${mc.summary.probPositive.toFixed(1)}%` : '--'} trend="up" />
                    <Metric label="5th Pctl Final Equity" value={mc ? formatMultiple(mc.summary.var95, 3) : '--'} />
                    <Metric label="Median Return" value={mc ? ((mc.summary.medianFinalValue - 1) * 100).toFixed(1) + '%' : '--'} trend="up" />
                    <Metric label="Worst Drawdown" value={mc ? mc.summary.worstDrawdown.toFixed(1) + '%' : '--'} trend="down" />
                    <Metric label="10th–90th Final Equity" value={mc ? `${formatMultiple(mc.summary.p10)} – ${formatMultiple(mc.summary.p90)}` : '--'} />
                    
                    <div className="pt-4 border-t border-slate-500/20">
                        <div className="p-4 bg-amber-400/10 border border-amber-300/25 rounded-xl">
                            <div className="flex items-center gap-2 mb-2">
                                <Shield size={12} className="text-amber-300" />
                                <span className="text-[10px] font-mono font-bold text-white uppercase">Resampling assumptions</span>
                            </div>
                            <p className="text-[10px] text-slate-300/80 leading-relaxed font-mono">
                                {mc ? `${mc.assumptions.method.replaceAll('_', ' ')}, seed ${mc.assumptions.seed}, ${mc.assumptions.inputObservations} observed simple returns${mc.assumptions.blockSize ? `, block size ${mc.assumptions.blockSize}` : ''}.` : 'Choose a named resampling method. Every run uses an explicit reproducibility seed.'}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StressView;
