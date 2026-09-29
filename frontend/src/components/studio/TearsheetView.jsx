"use client";
import React, { useEffect, useRef } from 'react';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import { setupHiDPI, createResizeObserver, exportCanvasToPNG } from './visual-kernel/canvas';
import { createLinearScale } from './visual-kernel/scales';
import { canonicalMetric, downloadStudioResultsCsv, downloadStudioResultsHtml, downloadStudioResultsJson, formatCanonicalMetric, observedReturnDiagnostics, replayFillLinkage } from '@/lib/studioResults';
import VirtualTradeLedger from './results/VirtualTradeLedger';
import { PortfolioAnalysis } from './PortfolioView';
import { 
    TrendingUp, TrendingDown, Activity, Shield, Target,
    Zap, ArrowUpRight, ArrowDownRight, PieChart, Download, AlertTriangle, Database
} from 'lucide-react';

// Metric Card Component
const MetricCard = ({ label, value, trend, color, icon: Icon, subtitle, large = false }) => (
    <div title={subtitle || undefined} className={`bg-[#0f0f14] border border-white/5 rounded-xl ${large ? 'p-5' : 'p-4'} hover:border-white/10 transition-all group`}>
        <div className="flex items-start justify-between mb-2">
            <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-widest">{label}</span>
            {Icon && <Icon size={14} className="text-[#64748b] group-hover:text-white/40 transition-colors" />}
        </div>
        <div className={`font-mono font-bold ${large ? 'text-2xl' : 'text-lg'} ${
            color === 'green' ? 'text-emerald-400' :
            color === 'red' ? 'text-red-400' :
            color === 'amber' ? 'text-amber-400' :
            'text-white'
        }`}>
            {value}
        </div>
        {subtitle && (
            <div className="text-[10px] font-mono text-[#64748b] mt-1">{subtitle}</div>
        )}
        {trend && (
            <div className={`flex items-center gap-1 mt-2 text-[10px] font-mono ${trend > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {trend > 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                {Math.abs(trend).toFixed(1)}% vs benchmark
            </div>
        )}
    </div>
);

// Equity Curve Chart — uses visual-kernel scales + HiDPI helper (P4-W1)
const EquityCurveChart = ({ data, grossData = [], benchmarkData = [] }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    
    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container || data.length === 0) return;
        const draw = (rect) => {
            const { ctx, width, height } = setupHiDPI(canvas, rect);
        ctx.fillStyle = '#0a0a0f';
        ctx.fillRect(0, 0, width, height);
        
        const padding = { top: 20, right: 60, bottom: 30, left: 20 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        
        const allValues = [...data,
            ...(grossData.length === data.length ? grossData : []),
            ...(benchmarkData.length === data.length ? benchmarkData : [])];
        const minVal = Math.min(...allValues) * 0.98;
        const maxVal = Math.max(...allValues) * 1.02;
        
        const xScale = createLinearScale([0, data.length - 1], [padding.left, padding.left + chartWidth]);
        const yScale = createLinearScale([minVal, maxVal], [padding.top + chartHeight, padding.top]);
        const scaleX = (i) => xScale(i);
        const scaleY = (v) => yScale(v);
        
        // Grid
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 5; i++) {
            const y = padding.top + (chartHeight / 5) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(rect.width - padding.right, y);
            ctx.stroke();
        }
        
        // Fill gradient
        const gradient = ctx.createLinearGradient(0, padding.top, 0, rect.height - padding.bottom);
        gradient.addColorStop(0, 'rgba(255,214,10,0.15)');
        gradient.addColorStop(1, 'rgba(255,214,10,0)');
        
        ctx.beginPath();
        ctx.moveTo(scaleX(0), rect.height - padding.bottom);
        data.forEach((v, i) => ctx.lineTo(scaleX(i), scaleY(v)));
        ctx.lineTo(scaleX(data.length - 1), rect.height - padding.bottom);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();
        
        // Line
        if (benchmarkData.length === data.length) {
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(56,189,248,0.8)';
            ctx.setLineDash([2, 3]);
            benchmarkData.forEach((v, i) => {
                if (i === 0) ctx.moveTo(scaleX(i), scaleY(v));
                else ctx.lineTo(scaleX(i), scaleY(v));
            });
            ctx.stroke();
            ctx.setLineDash([]);
        }
        if (grossData.length === data.length) {
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(148,163,184,0.55)';
            ctx.setLineDash([4, 4]);
            grossData.forEach((v, i) => {
                if (i === 0) ctx.moveTo(scaleX(i), scaleY(v));
                else ctx.lineTo(scaleX(i), scaleY(v));
            });
            ctx.stroke();
            ctx.setLineDash([]);
        }
        ctx.beginPath();
        ctx.strokeStyle = '#ffd60a';
        ctx.lineWidth = 2;
        data.forEach((v, i) => {
            if (i === 0) ctx.moveTo(scaleX(i), scaleY(v));
            else ctx.lineTo(scaleX(i), scaleY(v));
        });
        ctx.stroke();
        
        ctx.fillStyle = '#64748b';
        ctx.font = '10px JetBrains Mono';
        ctx.textAlign = 'left';
        for (let i = 0; i <= 4; i++) {
            const val = minVal + (maxVal - minVal) * (1 - i / 4);
            const y = padding.top + (chartHeight / 4) * i;
            ctx.fillText(`$${val.toFixed(0)}`, width - padding.right + 5, y + 4);
        }
        };
        draw(container.getBoundingClientRect());
        const cleanup = createResizeObserver(container, draw);
        return () => cleanup();
    }, [data, grossData, benchmarkData]);
    return (
        <div ref={containerRef} className="relative h-full">
            <canvas ref={canvasRef} className="w-full h-full" style={{ display: 'block' }} role="img" aria-label="Equity curve chart" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') e.currentTarget.blur(); }} />
            <div className="absolute top-2 left-3 text-[9px] font-mono text-[#64748b] uppercase tracking-widest">Net equity <span className="text-slate-500">/ gross dashed gray / benchmark dotted blue</span></div>
            <button aria-label="Export equity curve as PNG" onClick={() => exportCanvasToPNG(canvasRef.current, 'equity-curve.png')} className="absolute top-2 right-2 text-[8px] font-mono text-[#64748b] hover:text-white border border-white/10 rounded px-2 py-1 bg-black/30">PNG</button>
            <table className="sr-only" aria-label="Equity curve data table"><tbody>{data.slice(0, 20).map((v, i) => (<tr key={i}><td>{i}</td><td>{Number.isFinite(v) ? v.toFixed(2) : '--'}</td></tr>))}</tbody></table>
        </div>
    );
};

// Drawdown Chart — uses visual-kernel (P4-W1)
const DrawdownChart = ({ data }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container || data.length === 0) return;
        const draw = (rect) => {
        const { ctx, width, height } = setupHiDPI(canvas, rect);
        ctx.fillStyle = '#0a0a0f';
        ctx.fillRect(0, 0, width, height);
        const drawdowns = data.map(value => value * 100);
        const padding = { top: 20, right: 50, bottom: 20, left: 20 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        const minDD = Math.min(...drawdowns);
        const xScale = createLinearScale([0, data.length - 1], [padding.left, padding.left + chartWidth]);
        const yScale = createLinearScale([minDD, 0], [padding.top + chartHeight, padding.top]);
        const scaleX = (i) => xScale(i);
        const scaleY = (v) => yScale(v);
        
        // Fill
        ctx.beginPath();
        ctx.moveTo(scaleX(0), padding.top);
        drawdowns.forEach((v, i) => ctx.lineTo(scaleX(i), scaleY(v)));
        ctx.lineTo(scaleX(drawdowns.length - 1), padding.top);
        ctx.closePath();
        ctx.fillStyle = 'rgba(239,68,68,0.15)';
        ctx.fill();
        
        // Line
        ctx.beginPath();
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 1.5;
        drawdowns.forEach((v, i) => {
            if (i === 0) ctx.moveTo(scaleX(i), scaleY(v));
            else ctx.lineTo(scaleX(i), scaleY(v));
        });
        ctx.stroke();
        
        // Max DD label
        const maxDDIdx = drawdowns.indexOf(minDD);
        ctx.fillStyle = '#ef4444';
        ctx.font = 'bold 10px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(`${minDD.toFixed(1)}%`, scaleX(maxDDIdx), scaleY(minDD) + 14);
        };
        draw(container.getBoundingClientRect());
        const cleanup = createResizeObserver(container, draw);
        return () => cleanup();
    }, [data]);
    return (
        <div ref={containerRef} className="relative h-full">
            <canvas ref={canvasRef} className="w-full h-full" style={{ display: 'block' }} role="img" aria-label="Drawdown chart" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} />
            <div className="absolute top-2 left-3 text-[9px] font-mono text-[#64748b] uppercase tracking-widest">Drawdown</div>
            <button aria-label="Export drawdown as PNG" onClick={() => exportCanvasToPNG(canvasRef.current, 'drawdown.png')} className="absolute top-2 right-2 text-[8px] font-mono text-[#64748b] hover:text-white border border-white/10 rounded px-2 py-1 bg-black/30">PNG</button>
            <table className="sr-only" aria-label="Drawdown data table"><tbody>{data.slice(0, 20).map((v, i) => (<tr key={i}><td>{i}</td><td>{Number.isFinite(v) ? v.toFixed(2) : '--'}</td></tr>))}</tbody></table>
        </div>
    );
};

const ResultSeriesStrip = ({ series }) => {
    const cards = [
        ['Exposure', series?.exposure, value => `${(value * 100).toFixed(0)}%`],
        ['Turnover', series?.turnover, value => value.toFixed(2)],
        ['Trading cost', series?.costs, value => `${(value * 100).toFixed(2)}%`],
    ];
    return (
        <div className="grid grid-cols-3 gap-3">
            {cards.map(([label, values, format]) => {
                const observed = Array.isArray(values) ? values.filter(Number.isFinite) : [];
                const latest = observed.at(-1);
                const total = observed.reduce((sum, value) => sum + value, 0);
                return (
                    <div key={label} className="rounded-xl border border-white/5 bg-[#0f0f14] p-4">
                        <div className="text-[9px] font-mono uppercase tracking-widest text-[#64748b]">{label}</div>
                        <div className="mt-2 font-mono text-lg font-bold text-white">{latest === undefined ? 'Unavailable' : format(label === 'Exposure' ? latest : total)}</div>
                        <div className="mt-1 text-[9px] font-mono text-[#64748b]">{label === 'Exposure' ? 'latest observed gross exposure' : 'sum across returned bars'}</div>
                    </div>
                );
            })}
        </div>
    );
};

const FactorUnavailable = () => (
    <div className="flex min-h-[180px] flex-col items-center justify-center rounded-xl border border-white/5 bg-[#0f0f14] p-6 text-center">
        <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-white">Factor attribution unavailable</div>
        <p className="mt-2 max-w-xs text-[10px] font-mono leading-relaxed text-[#64748b]">
            This execution contract does not return complete factor exposures. No attribution estimate is shown.
        </p>
    </div>
);

const ReturnDiagnostics = ({ equity }) => {
    const diagnostics = observedReturnDiagnostics(equity);
    if (!diagnostics) return <div className="rounded-xl border border-white/5 bg-[#0f0f14] p-4 text-[10px] font-mono text-[#64748b]">Return diagnostics unavailable: at least two valid equity transitions are required.</div>;
    const maximum = Math.max(...diagnostics.histogram, 1);
    const pct = (value) => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : 'Unavailable';
    const rolling = diagnostics.rollingVolatility;
    return <section aria-label="Observed return diagnostics" className="rounded-xl border border-white/5 bg-[#0f0f14] p-4">
        <div className="text-[9px] font-mono uppercase tracking-widest text-[#64748b]">Observed net-return distribution and stability</div>
        <div className="mt-1 text-[8px] font-mono text-[#475569]">Descriptive values derived from {diagnostics.observations} returned equity transitions; no forecast or fitted regime is inferred.</div>
        <div className="mt-4 grid grid-cols-6 gap-3 text-[9px] font-mono">{[['P1', diagnostics.quantiles.p1], ['P5', diagnostics.quantiles.p5], ['Median', diagnostics.quantiles.median], ['P95', diagnostics.quantiles.p95], ['P99', diagnostics.quantiles.p99], ['ES 5%', diagnostics.expectedShortfall5]].map(([label, value]) => <div key={label}><div className="text-[#64748b]">{label}</div><div className="mt-1 text-sm font-bold text-white">{pct(value)}</div></div>)}</div>
        <div className="mt-4 flex h-20 items-end gap-1" aria-label="Return histogram">{diagnostics.histogram.map((count, index) => <div key={index} title={`bin ${index + 1}: ${count}`} className="flex-1 bg-amber-400/60" style={{ height: `${Math.max(4, count / maximum * 100)}%` }} />)}</div>
        <div className="mt-3 grid grid-cols-3 gap-3 border-t border-white/5 pt-3 text-[9px] font-mono text-[#64748b]"><div>Worst <strong className="text-red-300">{pct(diagnostics.worst)}</strong></div><div>Best <strong className="text-emerald-300">{pct(diagnostics.best)}</strong></div><div>{diagnostics.rollingWindow}-bar realized vol <strong className="text-white">{rolling.length ? pct(rolling.at(-1)) : 'Unavailable'}</strong></div></div>
        <div className="mt-3 border-l-2 border-white/10 pl-3 text-[9px] font-mono text-[#64748b]">Regime attribution unavailable: this execution artifact contains no governed regime labels.</div>
    </section>;
};

const SupportedAttribution = ({ trades, metrics }) => {
    const observed = (trades || []).map((trade) => ({ direction: trade.direction, value: trade.pnl_pct ?? trade.pnl })).filter((row) => Number.isFinite(row.value));
    const summarize = (direction) => { const rows = observed.filter((row) => row.direction === direction); return { count: rows.length, contribution: rows.reduce((sum, row) => sum + row.value, 0) }; };
    const long = summarize(1);
    const short = summarize(-1);
    const costDrag = canonicalMetric(metrics, 'cost_drag');
    const value = (number) => Number.isFinite(number) ? `${number >= 0 ? '+' : ''}${(number * 100).toFixed(2)}%` : 'Unavailable';
    return <section aria-label="Supported attribution" className="rounded-xl border border-white/5 bg-[#0f0f14] p-4">
        <div className="text-[9px] font-mono uppercase tracking-widest text-[#64748b]">Supported attribution</div>
        <div className="mt-4 grid grid-cols-3 gap-3 font-mono"><div><div className="text-[9px] text-[#64748b]">Long closed trades</div><div className="mt-1 text-sm font-bold text-white">{value(long.contribution)}</div><div className="text-[8px] text-[#475569]">sum across {long.count} observed trade returns</div></div><div><div className="text-[9px] text-[#64748b]">Short closed trades</div><div className="mt-1 text-sm font-bold text-white">{value(short.contribution)}</div><div className="text-[8px] text-[#475569]">sum across {short.count} observed trade returns</div></div><div><div className="text-[9px] text-[#64748b]">Execution-cost drag</div><div className="mt-1 text-sm font-bold text-red-300">{formatCanonicalMetric(costDrag)}</div><div className="text-[8px] text-[#475569]">{costDrag.methodology}</div></div></div>
        <div className="mt-3 border-l-2 border-white/10 pl-3 text-[9px] font-mono text-[#64748b]">Factor, sector, and multi-asset attribution unavailable: this single-asset execution artifact does not provide governed exposures or holdings.</div>
    </section>;
};

// Factor Attribution Chart (Axioma Style)
const FactorChart = ({ factors }) => {
    if (!factors) return <FactorUnavailable />;
    
    const factorList = [
        { key: 'momentum', name: 'Momentum', color: '#ffd60a' },
        { key: 'value', name: 'Value', color: '#22c55e' },
        { key: 'quality', name: 'Quality', color: '#3b82f6' },
        { key: 'lowVol', name: 'Low Vol', color: '#8b5cf6' },
        { key: 'size', name: 'Size', color: '#06b6d4' },
        { key: 'alpha', name: 'Pure Alpha', color: '#f59e0b' }
    ];
    
    const factorValues = factorList.map((factor) => factors[factor.key]);
    const total = factorValues.reduce((sum, value) => sum + value, 0);
    if (!factorValues.every(Number.isFinite) || !Number.isFinite(total) || total === 0) {
        return <FactorUnavailable />;
    }
    const primaryFactor = factorList.reduce((primary, candidate) => (
        factors[candidate.key] > factors[primary.key] ? candidate : primary
    ));
    
    return (
        <div className="bg-[#0f0f14] border border-white/5 rounded-xl p-4">
            <div className="text-[9px] font-mono text-[#64748b] uppercase tracking-widest mb-3">Factor Attribution</div>
            <div className="space-y-2">
                {factorList.map(f => {
                    const pct = (factors[f.key] / total) * 100;
                    return (
                        <div key={f.key} className="flex items-center gap-3">
                            <span className="text-[10px] font-mono text-[#64748b] w-20">{f.name}</span>
                            <div className="flex-1 h-5 bg-white/5 rounded-full overflow-hidden relative">
                                <div 
                                    className="h-full rounded-full transition-all" 
                                    style={{ width: `${pct}%`, backgroundColor: f.color }}
                                />
                            </div>
                            <span className="text-[10px] font-mono font-bold w-12 text-right" style={{ color: f.color }}>
                                {pct.toFixed(0)}%
                            </span>
                        </div>
                    );
                })}
            </div>
            <div className="mt-4 pt-3 border-t border-white/5">
                <div className="text-[9px] font-mono text-[#64748b]">
                    <span className="text-amber-500">{((factors.alpha / total) * 100).toFixed(0)}%</span> of returns attributable to pure alpha. 
                    Primary factor exposure: <span className="text-white">{primaryFactor.name}</span>
                </div>
            </div>
        </div>
    );
};

// Monthly Returns Heatmap
const MonthlyHeatmap = ({ trades }) => {
    // Group trades by month
    const monthlyReturns = {};
    trades.forEach(t => {
        const date = new Date(t.exit_date);
        const tradeReturn = t.pnl_pct ?? t.pnl;
        if (!Number.isFinite(tradeReturn) || Number.isNaN(date.getTime())) return;
        const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        if (!monthlyReturns[key]) monthlyReturns[key] = 0;
        monthlyReturns[key] += tradeReturn;
    });
    
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const years = [...new Set(Object.keys(monthlyReturns).map(k => k.split('-')[0]))].sort();
    
    return (
        <div className="bg-[#0f0f14] border border-white/5 rounded-xl p-4">
            <div className="text-[9px] font-mono text-[#64748b] uppercase tracking-widest mb-1">Closed-trade return sum by exit month</div>
            <div className="mb-3 text-[8px] font-mono text-[#475569]">Trade attribution view, not portfolio monthly performance</div>
            <div className="grid grid-cols-13 gap-1 text-[8px] font-mono">
                <div className="text-[#64748b]"></div>
                {months.map(m => (
                    <div key={m} className="text-center text-[#64748b]">{m}</div>
                ))}
                {years.map(year => (
                    <React.Fragment key={year}>
                        <div className="text-[#64748b] pr-2">{year}</div>
                        {months.map((_, mIdx) => {
                            const key = `${year}-${String(mIdx + 1).padStart(2, '0')}`;
                            const hasReturn = Object.prototype.hasOwnProperty.call(monthlyReturns, key);
                            const ret = hasReturn ? monthlyReturns[key] : null;
                            const intensity = hasReturn ? Math.min(Math.abs(ret) / 0.1, 1) : 0;
                            return (
                                <div 
                                    key={key}
                                    className="aspect-square rounded flex items-center justify-center text-[7px]"
                                    style={{
                                        backgroundColor: hasReturn && ret > 0
                                            ? `rgba(34,197,94,${0.15 + intensity * 0.6})`
                                            : hasReturn && ret < 0
                                            ? `rgba(239,68,68,${0.15 + intensity * 0.6})`
                                            : 'rgba(255,255,255,0.03)',
                                        color: hasReturn ? '#fff' : '#64748b'
                                    }}
                                    title={hasReturn ? `${key}: ${(ret * 100).toFixed(1)}%` : `${key}: no closed trades`}
                                >
                                    {hasReturn ? `${(ret * 100).toFixed(0)}` : '-'}
                                </div>
                            );
                        })}
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
};

const OrdersFillsPanel = ({ orders, linkage }) => (
    <section aria-label="Observed orders and fills" className="rounded-xl border border-white/5 bg-[#0f0f14] p-4">
        <div className="text-[9px] font-mono uppercase tracking-widest text-[#64748b]">Observed orders and fills</div>
        {(orders || []).length ? (
            <div className="mt-3 max-h-48 overflow-auto">
                <table className="w-full text-[10px] font-mono">
                    <thead><tr className="text-left text-[#64748b]"><th className="py-1 pr-3">Order</th><th className="py-1 pr-3">Date</th><th className="py-1 pr-3">Direction</th><th className="py-1 pr-3">Price</th><th className="py-1">Source</th></tr></thead>
                    <tbody>{orders.slice(0, 100).map((order) => <tr key={order.order_id} className="border-t border-white/5 text-slate-200"><td className="py-1 pr-3">{order.order_id}</td><td className="py-1 pr-3">{order.date || 'Unavailable'}</td><td className="py-1 pr-3">{order.direction}</td><td className="py-1 pr-3">{Number.isFinite(order.price) ? order.price.toFixed(2) : 'Unavailable'}</td><td className="py-1 text-slate-500">{order.source}</td></tr>)}</tbody>
                </table>
                {orders.length > 100 && <div className="mt-1 text-[9px] font-mono text-[#64748b]">Showing first 100 of {orders.length} observed orders.</div>}
            </div>
        ) : <div className="mt-2 text-[10px] font-mono text-[#64748b]">No observed orders: this artifact contains no nonzero-direction signals.</div>}
        <div className="mt-3 border-l-2 border-white/10 pl-3 text-[9px] font-mono text-[#64748b]">Fills unavailable: {linkage.fillsReason}</div>
    </section>
);

const TearsheetView = () => {
    const data = useStudioResultStore((state) => state.data);
    const setPlayIndex = useStudioResultStore((state) => state.setPlayIndex);
    const ticker = useStudioWorkspaceStore((state) => state.ticker);
    const setActiveTab = useStudioWorkspaceStore((state) => state.setActiveTab);
    const portfolioArtifact = useStudioResultStore((state) => state.portfolioArtifact);
    const { metrics, trades, orders, fillsStatus, equityCurve, series, metadata, runId } = data;
    
    const hasData = equityCurve && equityCurve.length > 0;
    
    if (!hasData) {
        if (portfolioArtifact) {
            return <div className="flex-1 overflow-y-auto bg-[#020204] p-6"><header className="mb-5 border-b border-white/10 pb-4"><h2 className="text-sm font-bold tracking-wide text-white">Portfolio results</h2><p className="mt-1 font-mono text-[10px] text-slate-500">Canonical artifact {portfolioArtifact.artifact_id}</p></header><PortfolioAnalysis result={portfolioArtifact} /></div>;
        }
        return (
            <div className="flex-1 flex items-center justify-center bg-[#020204]">
                <div className="text-center opacity-30">
                    <PieChart size={48} className="mx-auto mb-4" />
                    <p className="text-sm font-mono uppercase tracking-widest">Execute a strategy to see tearsheet</p>
                    <p className="text-xs font-mono text-[#64748b] mt-2">Performance analytics will appear here</p>
                </div>
            </div>
        );
    }
    
    const metric = (name) => canonicalMetric(metrics, name);
    const metricValue = (name, options) => formatCanonicalMetric(metric(name), options);
    const warnings = Array.isArray(metadata?.warnings) ? metadata.warnings : [];
    const netEquity = series?.equity_net?.length ? series.equity_net : equityCurve;
    const grossEquity = series?.equity_gross || [];
    const drawdown = series?.drawdown || [];
    const benchmarkEquity = Array.isArray(series?.benchmark_equity) && series.benchmark_equity.length === netEquity.length ? series.benchmark_equity : [];
    const linkage = replayFillLinkage({ orders, fills: data.fills, fillsStatus });
    const openTradeOnChart = (trade) => {
        const signal = data.signals.find((candidate) => candidate.date === trade.entry_date);
        const index = Number.isInteger(signal?.idx) ? signal.idx : data.signals.indexOf(signal);
        if (index >= 0) {
            setPlayIndex(index);
            setActiveTab('develop');
        }
    };

    return (
        <div className="flex-1 flex flex-col bg-[#020204] overflow-y-auto">
            {/* Header */}
            <div className="h-14 px-6 border-b border-white/5 flex items-center justify-between bg-[#0a0a0f] flex-shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center">
                        <PieChart size={20} className="text-black" />
                    </div>
                    <div>
                        <h2 className="text-sm font-bold text-white tracking-wide">Performance Tearsheet</h2>
                        <p className="text-[10px] font-mono text-[#64748b] uppercase">{ticker} • {trades.length} Trades • {equityCurve.length} Days</p>
                    </div>
                </div>
                
                <div className="flex items-center gap-3">
                    <button onClick={() => downloadStudioResultsCsv({ metrics, series, metadata, runId }, `${ticker}-${runId || 'results'}.csv`)} className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-[9px] font-mono text-[#cbd5e1] hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500" aria-label="Export canonical results as CSV">
                        <Download size={13} /> CSV
                    </button>
                    <button onClick={() => downloadStudioResultsJson({ metrics, series, metadata, runId, orders, fillsStatus }, `${ticker}-${runId || 'results'}.json`)} className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-[9px] font-mono text-[#cbd5e1] hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500" aria-label="Export canonical results as JSON">
                        <Download size={13} /> JSON
                    </button>
                    <button onClick={() => downloadStudioResultsHtml({ metrics, series, metadata, runId, orders, fillsStatus }, `${ticker}-${runId || 'results'}.html`)} className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-[9px] font-mono text-[#cbd5e1] hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500" aria-label="Export print-friendly HTML report (save as PDF via print)">
                        <Download size={13} /> HTML
                    </button>
                    <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2">
                    <Database size={16} className="text-amber-500" />
                    <div>
                        <div className="text-[9px] font-mono text-[#64748b] uppercase">Persisted run</div>
                        <div className="max-w-[180px] truncate text-xs font-bold font-mono text-white" title={runId || 'Legacy in-memory result'}>{runId || 'Legacy result'}</div>
                    </div>
                </div>
                </div>
            </div>
            
            <div className="p-6 space-y-6">
                {/* Key Metrics Grid */}
                <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/5 bg-[#0f0f14] px-4 py-3 text-[9px] font-mono text-[#8b95a7]">
                    <span>Engine: <strong className="text-white">{metadata?.provenance?.engine_version || 'Unavailable'}</strong></span>
                    <span>Convention: simple returns, 252 periods/year, population volatility</span>
                    <span>Currency: <strong className="text-white">{metadata?.data_quality?.currency || 'Not reported'}</strong></span>
                    <span>Calendar: <strong className="text-white">{metadata?.data_quality?.calendar || 'Not reported'}</strong></span>
                    {warnings.length > 0 && <span className="flex items-center gap-1 text-amber-400"><AlertTriangle size={11} /> {warnings.length} warning{warnings.length === 1 ? '' : 's'}</span>}
                </div>
                <div className="grid grid-cols-6 gap-3">
                    <MetricCard 
                        label="Total Return" 
                        value={metricValue('total_return', { signed: true })}
                        color={metric('total_return').value > 0 ? 'green' : 'red'}
                        icon={TrendingUp}
                        subtitle={metric('total_return').methodology}
                        large
                    />
                    <MetricCard 
                        label="Sharpe Ratio" 
                        value={metricValue('sharpe')}
                        color={metric('sharpe').value > 1.5 ? 'green' : metric('sharpe').value > 1 ? 'amber' : 'red'}
                        icon={Target}
                        subtitle={metric('sharpe').methodology}
                        large
                    />
                    <MetricCard 
                        label="Max Drawdown" 
                        value={metricValue('max_drawdown')}
                        color="red"
                        icon={TrendingDown}
                        subtitle={metric('max_drawdown').methodology}
                        large
                    />
                    <MetricCard 
                        label="Win Rate" 
                        value={metricValue('hit_rate', { digits: 1 })}
                        color={metric('hit_rate').value > 0.55 ? 'green' : 'amber'}
                        icon={Zap}
                        subtitle={`${metricValue('total_trades')} closed trades; ${metric('hit_rate').methodology}`}
                        large
                    />
                    <MetricCard 
                        label="CAGR" 
                        value={metricValue('annual_return')}
                        color={metric('annual_return').value > 0.1 ? 'green' : 'amber'}
                        icon={Activity}
                        subtitle={metric('annual_return').methodology}
                        large
                    />
                    <MetricCard 
                        label="Calmar Ratio" 
                        value={metricValue('calmar')}
                        color={metric('calmar').value > 2 ? 'green' : 'amber'}
                        icon={Shield}
                        subtitle={metric('calmar').methodology}
                        large
                    />
                </div>
                
                {/* Charts Row */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="bg-[#0f0f14] border border-white/5 rounded-xl h-[200px] overflow-hidden">
                        <EquityCurveChart data={netEquity} grossData={grossEquity} benchmarkData={benchmarkEquity} />
                    </div>
                    <div className="bg-[#0f0f14] border border-white/5 rounded-xl h-[200px] overflow-hidden">
                        {drawdown.length ? <DrawdownChart data={drawdown} /> : <div className="flex h-full items-center justify-center text-xs font-mono text-[#64748b]">Drawdown series unavailable</div>}
                    </div>
                </div>
                <ResultSeriesStrip series={series} />
                {!benchmarkEquity.length && <div className="rounded-xl border border-white/5 bg-[#0f0f14] p-3 text-[9px] font-mono text-[#64748b]">Benchmark overlay unavailable: this artifact carries no buy-and-hold benchmark series.</div>}
                <OrdersFillsPanel orders={orders} linkage={linkage} />
                <div className="rounded-xl border border-white/5 bg-[#0f0f14] p-3 text-[9px] font-mono text-[#64748b]">Arrow export deferred: no governed columnar schema exists yet; CSV and JSON carry the same canonical values. PDF is served via the print-friendly HTML export and the browser save-as-PDF dialog.</div>
                <ReturnDiagnostics equity={netEquity} />
                <SupportedAttribution trades={trades} metrics={metrics} />
                
                {/* Factor Attribution & Monthly Returns */}
                <div className="grid grid-cols-2 gap-4">
                    <FactorChart />
                    {trades.length > 0 && <MonthlyHeatmap trades={trades} />}
                </div>
                
                {/* Additional Metrics */}
                <div className="grid grid-cols-8 gap-2">
                    <MetricCard label="Avg Win" value={metricValue('average_win')} color="green" subtitle={metric('average_win').methodology} />
                    <MetricCard label="Avg Loss" value={metricValue('average_loss')} color="red" subtitle={metric('average_loss').methodology} />
                    <MetricCard label="Profit Factor" value={metricValue('payoff')} color="amber" subtitle={metric('payoff').methodology} />
                    <MetricCard label="Sortino" value={metricValue('sortino')} subtitle={metric('sortino').methodology} />
                    <MetricCard label="Avg Trade" value={metricValue('expectancy')} subtitle={metric('expectancy').methodology} />
                    <MetricCard label="Max Win" value={metricValue('max_win')} color="green" subtitle={metric('max_win').methodology} />
                    <MetricCard label="Max Loss" value={metricValue('max_loss')} color="red" subtitle={metric('max_loss').methodology} />
                    <MetricCard label="Volatility" value={metricValue('volatility')} subtitle={metric('volatility').methodology} />
                </div>
                <section aria-labelledby="results-trades-heading" className="space-y-3">
                    <div><h3 id="results-trades-heading" className="text-[10px] font-mono font-bold uppercase tracking-widest text-white">Execution records</h3><p className="mt-1 text-[9px] font-mono text-[#64748b]">Virtualized closed-trade rows. Select a row to open its entry on the chart.</p></div>
                    <VirtualTradeLedger trades={trades} onSelect={openTradeOnChart} />
                </section>
            </div>
        </div>
    );
};

export default TearsheetView;
