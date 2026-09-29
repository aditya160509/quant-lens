"use client";

import React, { useMemo, useState } from "react";
import { studioRequest } from "@/lib/studioApi";
import { useStudioResultStore } from "@/stores/studio/resultStore";

const pct = (value) => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "Unavailable";
const number = (value, digits = 3) => Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";

export default function AdvancedValidationView() {
    const data = useStudioResultStore((state) => state.data);
    const portfolio = useStudioResultStore((state) => state.portfolioArtifact);
    const portfolioVersion = useStudioResultStore((state) => state.portfolioVersion);
    const wfJob = useStudioResultStore((state) => state.wfJob);
    const audit = useStudioResultStore((state) => state.promotionAuditRecords);
    const [source, setSource] = useState(portfolio ? "portfolio" : "strategy");
    const [trials, setTrials] = useState(1);
    const [benchmark, setBenchmark] = useState(0);
    const [segments, setSegments] = useState("[]");
    const [trades, setTrades] = useState("[]");
    const [alternatives, setAlternatives] = useState("{}");
    const [portfolioValue, setPortfolioValue] = useState("");
    const [holdingDays, setHoldingDays] = useState(1);
    const [evidence, setEvidence] = useState({});
    const [certification, setCertification] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState("");
    const strategyReturns = useMemo(() => (data.equityCurve || []).slice(1).map((value, index) => value / data.equityCurve[index] - 1).filter(Number.isFinite), [data.equityCurve]);
    const returns = source === "portfolio" ? portfolio?.observed_portfolio_returns || [] : strategyReturns;
    const post = async (key, path, body) => {
        setBusy(key); setError("");
        try { const response = await studioRequest(path, { method: "POST", retries: 0, body }); setEvidence((current) => ({ ...current, [key]: response.evidence })); }
        catch (cause) { setError(cause?.message || "Advanced validation failed."); }
        finally { setBusy(""); }
    };
    const certify = async () => {
        if (!portfolioVersion?.version_id || !wfJob?.job_id) { setError("Certification requires the saved portfolio version and its completed validation job."); return; }
        const tests = Object.entries(evidence).map(([name]) => ({ name, status: "passed" }));
        if (!evidence.implementation) tests.push({ name: "implementation_feasibility", status: "skipped", reason: "not run by the user" });
        if (!evidence.substitution) tests.push({ name: "data_substitution", status: "skipped", reason: "not run by the user" });
        setBusy("certification"); setError("");
        try {
            const response = await studioRequest("/validation/certifications", { method: "POST", retries: 0, body: {
                source: { type: "portfolio_version", id: portfolioVersion.version_id }, validation_job_id: wfJob.job_id,
                tests, thresholds: wfJob.result?.verdict?.thresholds || {}, overrides: audit.filter((record) => record.action === "override"),
            } }); setCertification(response.certification);
        } catch (cause) { setError(cause?.message || "Certification could not be created."); }
        finally { setBusy(""); }
    };
    return <div className="flex min-h-0 flex-1 flex-col overflow-auto bg-[#050812] p-6 text-slate-200">
        <header className="flex items-end justify-between border-b border-white/10 pb-4"><div><h2 className="text-sm font-semibold text-white">Advanced evidence</h2><p className="mt-1 font-mono text-[10px] text-slate-500">Opt-in statistical and implementation diagnostics</p></div><label className="text-[9px] uppercase text-slate-500">Source <select value={source} onChange={(event) => setSource(event.target.value)} className="ml-2 h-8 border border-white/10 bg-[#080c14] px-2 text-white"><option value="strategy">Strategy returns</option>{portfolio ? <option value="portfolio">Portfolio returns</option> : null}</select></label></header>
        {error ? <div role="alert" className="mt-4 border-l-2 border-red-400 pl-3 text-[10px] text-red-300">{error}</div> : null}
        <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <section className="border-t border-white/10 pt-4"><div className="flex items-center justify-between"><div><h3 className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Selection-adjusted Sharpe</h3><p className="mt-1 text-[9px] text-slate-600">{returns.length} supplied observations</p></div><button type="button" disabled={busy || returns.length < 30} onClick={() => post("sharpe", "/validation/advanced/sharpe", { returns, trials: Number(trials), benchmark_sharpe: Number(benchmark) })} className="border border-amber-400/40 px-3 py-2 text-[8px] uppercase text-amber-300 disabled:opacity-30">Run</button></div><div className="mt-3 flex gap-2"><label className="text-[8px] uppercase text-slate-600">Trials<input aria-label="Strategy trials" type="number" min="1" max="100000" value={trials} onChange={(event) => setTrials(event.target.value)} className="ml-2 h-7 w-20 border border-white/10 bg-[#080c14] px-2 text-white" /></label><label className="text-[8px] uppercase text-slate-600">Benchmark Sharpe<input aria-label="Benchmark Sharpe" type="number" step="0.1" value={benchmark} onChange={(event) => setBenchmark(event.target.value)} className="ml-2 h-7 w-20 border border-white/10 bg-[#080c14] px-2 text-white" /></label></div>{evidence.sharpe ? <dl className="mt-4 grid grid-cols-2 gap-px bg-white/10">{[["Observed Sharpe", number(evidence.sharpe.annualized_sharpe)], ["PSR", pct(evidence.sharpe.probabilistic_sharpe_probability)], ["Deflated probability", pct(evidence.sharpe.deflated_sharpe_probability)], ["Null max Sharpe", number(evidence.sharpe.selection_bias.expected_max_null_annualized_sharpe)]].map(([label, value]) => <div key={label} className="bg-[#080c14] p-3"><dt className="text-[8px] uppercase text-slate-600">{label}</dt><dd className="mt-1 font-mono text-sm">{value}</dd></div>)}</dl> : null}</section>
            <section className="border-t border-white/10 pt-4"><div className="flex items-center justify-between"><h3 className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Parameter instability</h3><button type="button" disabled={busy} onClick={() => { try { post("instability", "/validation/advanced/parameter-instability", { segments: JSON.parse(segments) }); } catch { setError("Segments must be valid JSON."); } }} className="border border-amber-400/40 px-3 py-2 text-[8px] uppercase text-amber-300 disabled:opacity-30">Run</button></div><textarea aria-label="Parameter segments JSON" value={segments} onChange={(event) => setSegments(event.target.value)} className="mt-3 h-28 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[9px]" />{evidence.instability ? <div className="mt-3 font-mono text-[9px] text-slate-400">Range {number(evidence.instability.diagnostics.sharpe_range)} · dispersion {number(evidence.instability.diagnostics.sharpe_std)} · sign flip {String(evidence.instability.diagnostics.sign_flip)} · worst {evidence.instability.diagnostics.worst_segment}</div> : null}</section>
            <section className="border-t border-white/10 pt-4"><div className="flex items-center justify-between"><h3 className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Implementation feasibility</h3><button type="button" disabled={busy} onClick={() => { try { post("implementation", "/validation/advanced/implementation", { trades: JSON.parse(trades), portfolio_value: portfolioValue === "" ? null : Number(portfolioValue), holding_days: Number(holdingDays) }); } catch { setError("Trades must be valid JSON."); } }} className="border border-amber-400/40 px-3 py-2 text-[8px] uppercase text-amber-300 disabled:opacity-30">Run</button></div><textarea aria-label="Feasibility trades JSON" value={trades} onChange={(event) => setTrades(event.target.value)} className="mt-3 h-28 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[9px]" /><div className="mt-2 flex gap-2"><input aria-label="Portfolio value" type="number" value={portfolioValue} onChange={(event) => setPortfolioValue(event.target.value)} placeholder="Portfolio value" className="h-7 flex-1 border border-white/10 bg-[#080c14] px-2 text-[9px]" /><input aria-label="Holding days" type="number" min="1" value={holdingDays} onChange={(event) => setHoldingDays(event.target.value)} className="h-7 w-24 border border-white/10 bg-[#080c14] px-2 text-[9px]" /></div>{evidence.implementation ? <div className="mt-3 text-[9px] text-slate-400">Turnover {pct(evidence.implementation.summary.one_way_turnover)} · breaches {evidence.implementation.summary.capacity_breach_count}<div className="mt-1 text-slate-600">{evidence.implementation.skipped_tests.join(" · ") || "All supplied feasibility fields evaluated."}</div></div> : null}</section>
            <section className="border-t border-white/10 pt-4"><div className="flex items-center justify-between"><h3 className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Data-source substitution</h3><button type="button" disabled={busy || returns.length < 30} onClick={() => { try { post("substitution", "/validation/advanced/data-substitution", { primary: returns, alternatives: JSON.parse(alternatives) }); } catch { setError("Alternatives must be valid JSON."); } }} className="border border-amber-400/40 px-3 py-2 text-[8px] uppercase text-amber-300 disabled:opacity-30">Run</button></div><textarea aria-label="Alternative return sources JSON" value={alternatives} onChange={(event) => setAlternatives(event.target.value)} className="mt-3 h-28 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[9px]" />{evidence.substitution?.alternatives?.map((item) => <div key={item.source} className="mt-2 flex justify-between border-b border-white/5 pb-1 font-mono text-[9px]"><span>{item.source}</span><span>Sharpe Δ {number(item.sharpe_delta)} · MAD {number(item.mean_absolute_return_delta, 6)}</span></div>)}</section>
        </div>
        <section className="mt-6 flex items-center justify-between border-y border-white/10 py-4"><div><h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-300">Immutable certification</h3><p className="mt-1 text-[9px] text-slate-600">Includes every run or skipped test, thresholds, overrides, source hash, and validation hash.</p>{certification ? <div className="mt-2 font-mono text-[9px] text-emerald-300">{certification.certification_id} · {certification.content_hash}</div> : null}</div><button type="button" onClick={certify} disabled={busy || !Object.keys(evidence).length} className="border border-emerald-400/30 px-4 py-2 text-[8px] font-bold uppercase text-emerald-300 disabled:opacity-30">Create certification</button></section>
    </div>;
}
