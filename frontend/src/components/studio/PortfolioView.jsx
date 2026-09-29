"use client";

import React, { useMemo, useState } from "react";
import { studioRequest } from "@/lib/studioApi";
import { useStudioResultStore } from "@/stores/studio/resultStore";

const blankAsset = () => ({ ticker: "", expected: "", volatility: "", current: "" });
const initialAssets = [blankAsset(), blankAsset()];
const percent = (value) => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "Unavailable";

export function parseReturnCsv(text) {
    const lines = String(text || "").trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 4) throw new Error("Return CSV requires a header and at least 3 observations.");
    const header = lines[0].split(",").map((value) => value.trim());
    const hasDate = /^(date|time|timestamp)$/i.test(header[0]);
    const assets = (hasDate ? header.slice(1) : header).map((value) => value.toUpperCase());
    if (assets.length < 2 || assets.some((value) => !value) || new Set(assets).size !== assets.length) throw new Error("Return CSV requires at least 2 unique asset columns.");
    const observations = lines.slice(1).map((line, rowIndex) => {
        const cells = line.split(",").map((value) => value.trim());
        const values = (hasDate ? cells.slice(1) : cells).map(Number);
        if (values.length !== assets.length || values.some((value) => !Number.isFinite(value))) throw new Error(`Invalid return observation on row ${rowIndex + 2}.`);
        return values;
    });
    return { assets, observations };
}

export function parseHoldingsCsv(text) {
    const lines = String(text || "").trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 3) throw new Error("Holdings CSV requires a header and at least 2 assets.");
    const headers = lines[0].split(",").map((value) => value.trim().toLowerCase());
    const column = (names) => headers.findIndex((header) => names.includes(header));
    const tickerIndex = column(["ticker", "symbol", "asset"]);
    const weightIndex = column(["current_weight", "weight", "weight_pct"]);
    const valueIndex = column(["market_value", "value"]);
    const expectedIndex = column(["expected_return", "return", "return_pct"]);
    const volatilityIndex = column(["volatility", "vol", "volatility_pct"]);
    if (tickerIndex < 0 || (weightIndex < 0 && valueIndex < 0)) throw new Error("Holdings CSV requires ticker and current_weight or market_value columns.");
    const rows = lines.slice(1).map((line, rowIndex) => {
        const cells = line.split(",").map((value) => value.trim());
        const ticker = cells[tickerIndex]?.toUpperCase();
        const weight = weightIndex >= 0 ? Number(cells[weightIndex]) : null;
        const marketValue = valueIndex >= 0 ? Number(cells[valueIndex]) : null;
        if (!ticker || (weightIndex >= 0 && !Number.isFinite(weight)) || (valueIndex >= 0 && (!Number.isFinite(marketValue) || marketValue < 0))) throw new Error(`Invalid holding on row ${rowIndex + 2}.`);
        return { ticker, weight, marketValue, expected: expectedIndex >= 0 ? cells[expectedIndex] : "", volatility: volatilityIndex >= 0 ? cells[volatilityIndex] : "" };
    });
    if (new Set(rows.map((row) => row.ticker)).size !== rows.length) throw new Error("Holdings tickers must be unique.");
    const totalValue = valueIndex >= 0 ? rows.reduce((sum, row) => sum + row.marketValue, 0) : null;
    if (valueIndex >= 0 && totalValue <= 0) throw new Error("Holdings market value must have a positive total.");
    return rows.map((row) => ({
        ticker: row.ticker,
        current: weightIndex >= 0 ? String(row.weight) : String((row.marketValue / totalValue) * 100),
        expected: row.expected,
        volatility: row.volatility,
    }));
}

function Frontier({ points = [], selected }) {
    if (!points.length) return <div className="flex h-52 items-center justify-center text-[10px] text-slate-600">No feasible frontier returned.</div>;
    const values = [...points, selected].filter(Boolean);
    const minX = Math.min(...values.map((point) => point.volatility));
    const maxX = Math.max(...values.map((point) => point.volatility));
    const minY = Math.min(...values.map((point) => point.return));
    const maxY = Math.max(...values.map((point) => point.return));
    const x = (value) => 24 + ((value - minX) / (maxX - minX || 1)) * 292;
    const y = (value) => 176 - ((value - minY) / (maxY - minY || 1)) * 148;
    const path = points.map((point, index) => `${index ? "L" : "M"}${x(point.volatility)},${y(point.return)}`).join(" ");
    return <svg viewBox="0 0 340 200" role="img" aria-label="Efficient frontier, volatility versus expected return" className="h-52 w-full">
        <path d={path} fill="none" stroke="#64748b" strokeWidth="1.5" />
        {points.map((point, index) => <circle key={index} cx={x(point.volatility)} cy={y(point.return)} r="2" fill="#94a3b8" />)}
        {selected ? <circle cx={x(selected.volatility)} cy={y(selected.return)} r="5" fill="#fbbf24" stroke="#111827" strokeWidth="2" /> : null}
        <text x="170" y="197" textAnchor="middle" fill="#64748b" fontSize="9">Annualized volatility →</text>
        <text x="8" y="102" textAnchor="middle" fill="#64748b" fontSize="9" transform="rotate(-90 8 102)">Expected return →</text>
    </svg>;
}

export function PortfolioAnalysis({ result }) {
    if (!result) return <div className="flex min-h-[420px] items-center justify-center border-y border-white/10 text-center font-mono text-[10px] text-slate-600">Run optimization to generate a governed portfolio artifact.</div>;
    const metrics = [
        ["Expected return", percent(result.metrics.expected_return)], ["Volatility", percent(result.metrics.volatility)],
        ["Sharpe", result.metrics.sharpe?.toFixed(3) ?? "Unavailable"], ["Tracking error", percent(result.metrics.tracking_error)],
        ["Turnover", percent(result.metrics.turnover)], ["Est. cost", percent(result.metrics.estimated_cost_fraction)],
        ["Gross leverage", percent(result.metrics.gross_leverage)], ["Concentration", result.metrics.concentration_hhi.toFixed(3)],
    ];
    return <>
        <div className="flex items-start justify-between border-b border-white/10 pb-4"><div><div className="text-[9px] uppercase tracking-wider text-slate-600">Artifact</div><div className="mt-1 font-mono text-[11px] text-amber-300">{result.artifact_id}</div></div><div className="text-right text-[9px] text-slate-500">{result.engine_version}<br />{result.objective}</div></div>
        <dl className="my-5 grid grid-cols-4 gap-px bg-white/10">{metrics.map(([label, value]) => <div key={label} className="bg-[#080c14] p-3"><dt className="text-[9px] uppercase tracking-wider text-slate-600">{label}</dt><dd className="mt-1 font-mono text-sm text-white">{value}</dd></div>)}</dl>
        <div className="grid gap-6 lg:grid-cols-2"><div><h3 className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">Target and implementation</h3><div className="grid grid-cols-[1fr_repeat(3,70px)] border-b border-white/10 pb-1 text-right text-[8px] uppercase text-slate-600"><span className="text-left">Asset</span><span>Target</span><span>Trade</span><span>Risk</span></div>{result.assets.map((asset) => <div key={asset} className="grid grid-cols-[1fr_repeat(3,70px)] border-b border-white/5 py-2 font-mono text-[10px]"><span>{asset}</span><span className="text-right text-white">{percent(result.weights[asset])}</span><span className={`text-right ${result.trades[asset] >= 0 ? "text-emerald-300" : "text-red-300"}`}>{result.trades[asset] >= 0 ? "+" : ""}{percent(result.trades[asset])}</span><span className="text-right text-slate-500">{percent(result.risk_contribution[asset])}</span></div>)}</div><div><h3 className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">Efficient frontier</h3><Frontier points={result.frontier} selected={{ return: result.metrics.expected_return, volatility: result.metrics.volatility }} /></div></div>
        <div className="mt-6 grid gap-6 border-t border-white/10 pt-4 lg:grid-cols-2"><section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">Model diagnostics</h3><dl className="space-y-1 font-mono text-[9px]">{[["Expected returns", result.model.expected_returns], ["Covariance", result.model.covariance], ["Observations", result.model.observations ?? "Not applicable"], ["Periods / year", result.model.periods_per_year], ["Condition number", Number(result.model.condition_number).toPrecision(5)], ["Minimum eigenvalue", Number(result.model.minimum_eigenvalue).toExponential(3)], ["Shrinkage", result.model.shrinkage == null ? "Not applicable" : percent(result.model.shrinkage)]].map(([label, value]) => <div key={label} className="flex justify-between border-b border-white/5 py-1"><dt className="text-slate-600">{label}</dt><dd className="text-slate-300">{value}</dd></div>)}</dl></section><section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">Constraint exposures</h3>{result.constraint_exposures?.length ? result.constraint_exposures.map((item) => <div key={item.name} className="grid grid-cols-[1fr_repeat(3,60px)] border-b border-white/5 py-1 font-mono text-[9px]"><span>{item.name}</span><span className="text-right text-slate-300">{item.value.toFixed(4)}</span><span className="text-right text-slate-600">min {item.min ?? "—"}</span><span className="text-right text-slate-600">max {item.max ?? "—"}</span></div>) : <p className="text-[9px] text-slate-600">No user exposure constraints supplied.</p>}</section></div>
        {result.scenario_results?.length ? <section className="mt-6 border-t border-white/10 pt-4"><h3 className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">Scenario impact</h3>{result.scenario_results.map((scenario) => <div key={scenario.name} className="grid grid-cols-[1fr_100px] border-b border-white/5 py-2 font-mono text-[10px]"><span>{scenario.name}</span><span className={`text-right ${scenario.portfolio_return >= 0 ? "text-emerald-300" : "text-red-300"}`}>{percent(scenario.portfolio_return)}</span></div>)}</section> : null}
        {result.warnings?.length ? <div className="mt-5 border-l border-amber-400/40 pl-3 text-[9px] leading-relaxed text-slate-500">{result.warnings.join(" ")}</div> : null}
    </>;
}

export default function PortfolioView() {
    const setPortfolioArtifact = useStudioResultStore((state) => state.setPortfolioArtifact);
    const setPortfolioInputs = useStudioResultStore((state) => state.setPortfolioInputs);
    const setPortfolioVersion = useStudioResultStore((state) => state.setPortfolioVersion);
    const [assets, setAssets] = useState(initialAssets);
    const [inputMode, setInputMode] = useState("assumptions");
    const [source, setSource] = useState({ kind: "manual" });
    const [returnCsv, setReturnCsv] = useState("");
    const [returnObservations, setReturnObservations] = useState(null);
    const [expectedModel, setExpectedModel] = useState("supplied");
    const [covarianceModel, setCovarianceModel] = useState("supplied");
    const [shrinkage, setShrinkage] = useState(20);
    const [periodsPerYear, setPeriodsPerYear] = useState(252);
    const [objective, setObjective] = useState("max_sharpe");
    const [correlation, setCorrelation] = useState(0.1);
    const [maxWeight, setMaxWeight] = useState(70);
    const [minWeight, setMinWeight] = useState(0);
    const [grossLeverage, setGrossLeverage] = useState(100);
    const [costBps, setCostBps] = useState(10);
    const [maxTurnover, setMaxTurnover] = useState("");
    const [targetReturn, setTargetReturn] = useState("");
    const [covarianceOverride, setCovarianceOverride] = useState("");
    const [benchmarkWeights, setBenchmarkWeights] = useState("");
    const [linearConstraints, setLinearConstraints] = useState("");
    const [scenarios, setScenarios] = useState("");
    const [riskAversion, setRiskAversion] = useState(50);
    const [result, setResult] = useState(null);
    const [versions, setVersions] = useState([]);
    const [saveName, setSaveName] = useState("");
    const [compareLeft, setCompareLeft] = useState("");
    const [compareRight, setCompareRight] = useState("");
    const [comparison, setComparison] = useState(null);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const payload = useMemo(() => {
        const volatility = assets.map((asset) => Number(asset.volatility) / 100);
        let covariance = volatility.map((rowVol, row) => volatility.map((columnVol, column) => row === column ? rowVol ** 2 : rowVol * columnVol * Number(correlation)));
        if (covarianceOverride.trim()) {
            try { covariance = JSON.parse(covarianceOverride); }
            catch { covariance = null; }
        }
        let benchmark = null;
        let customConstraints = [];
        let scenarioDefinitions = [];
        try { if (benchmarkWeights.trim()) benchmark = JSON.parse(benchmarkWeights); } catch { benchmark = "invalid"; }
        try { if (linearConstraints.trim()) customConstraints = JSON.parse(linearConstraints); } catch { customConstraints = "invalid"; }
        try { if (scenarios.trim()) scenarioDefinitions = JSON.parse(scenarios); } catch { scenarioDefinitions = "invalid"; }
        return {
            assets: assets.map((asset) => asset.ticker.trim().toUpperCase()),
            expected_returns: assets.map((asset) => Number(asset.expected) / 100),
            covariance,
            return_observations: returnObservations,
            expected_return_model: expectedModel,
            covariance_model: covarianceModel,
            periods_per_year: Number(periodsPerYear),
            shrinkage: Number(shrinkage) / 100,
            current_weights: assets.map((asset) => Number(asset.current) / 100),
            objective,
            min_weight: Number(minWeight) / 100,
            max_weight: Number(maxWeight) / 100,
            gross_leverage: Number(grossLeverage) / 100,
            cost_bps: Number(costBps),
            max_turnover: maxTurnover === "" ? null : Number(maxTurnover) / 100,
            target_return: targetReturn === "" ? null : Number(targetReturn) / 100,
            benchmark_weights: benchmark,
            linear_constraints: customConstraints,
            scenarios: scenarioDefinitions,
            risk_aversion: Number(riskAversion) / 100,
            source,
        };
    }, [assets, benchmarkWeights, correlation, costBps, covarianceModel, covarianceOverride, expectedModel, grossLeverage, linearConstraints, maxTurnover, maxWeight, minWeight, objective, periodsPerYear, returnObservations, riskAversion, scenarios, shrinkage, source, targetReturn]);
    const updateAsset = (index, field, value) => setAssets((current) => current.map((asset, assetIndex) => assetIndex === index ? { ...asset, [field]: value } : asset));
    const optimize = async () => {
        setLoading(true); setError("");
        try {
            if (assets.some((asset) => !asset.ticker.trim())) throw new Error("Every asset requires a ticker.");
            if (expectedModel === "supplied" && assets.some((asset) => asset.expected === "")) throw new Error("Every asset requires an expected return for the supplied model.");
            if (covarianceModel === "supplied" && !covarianceOverride.trim() && assets.some((asset) => asset.volatility === "")) throw new Error("Every asset requires volatility for the supplied covariance model.");
            if (covarianceModel === "supplied" && covarianceOverride.trim() && !Array.isArray(payload.covariance)) throw new Error("Covariance override must be a valid JSON matrix.");
            if (benchmarkWeights.trim() && !Array.isArray(payload.benchmark_weights)) throw new Error("Benchmark weights must be a valid JSON array.");
            if (objective === "tracking_error" && !Array.isArray(payload.benchmark_weights)) throw new Error("Tracking-error optimization requires benchmark weights.");
            if (linearConstraints.trim() && !Array.isArray(payload.linear_constraints)) throw new Error("Linear constraints must be a valid JSON array.");
            if (scenarios.trim() && !Array.isArray(payload.scenarios)) throw new Error("Scenarios must be a valid JSON array.");
            const response = await studioRequest("/portfolio/optimize", { method: "POST", body: payload, retries: 0 });
            setResult(response.portfolio);
            setPortfolioArtifact(response.portfolio);
            setPortfolioInputs(payload);
            setPortfolioVersion(null);
        } catch (cause) { setError(cause?.message || "Portfolio optimization failed."); }
        finally { setLoading(false); }
    };
    const loadVersions = async () => {
        try { const response = await studioRequest("/portfolio/versions"); setVersions(response.versions || []); }
        catch (cause) { setError(cause?.message || "Portfolio versions could not be loaded."); }
    };
    const saveVersion = async () => {
        if (!result) return;
        if (!saveName.trim()) { setError("Enter a version name before saving."); return; }
        try {
            const response = await studioRequest("/portfolio/versions", { method: "POST", body: { name: saveName.trim(), artifact_id: result.artifact_id, inputs: payload }, retries: 0 });
            setVersions((current) => [response.version, ...current.filter((item) => item.version_id !== response.version.version_id)]);
            setPortfolioVersion(response.version);
            setSaveName(""); setError("");
        } catch (cause) { setError(cause?.message || "Portfolio version could not be saved."); }
    };
    const loadVersion = async (versionId) => {
        try { const response = await studioRequest(`/portfolio/versions/${encodeURIComponent(versionId)}`); const inputs = response.version.inputs; setResult(response.version.portfolio); setPortfolioArtifact(response.version.portfolio); setPortfolioInputs(inputs); setPortfolioVersion(response.version); setAssets(inputs.assets.map((ticker, index) => ({ ticker, expected: inputs.expected_returns?.[index] == null ? "" : String(inputs.expected_returns[index] * 100), volatility: inputs.covariance?.[index]?.[index] == null ? "" : String(Math.sqrt(inputs.covariance[index][index]) * 100), current: String((inputs.current_weights?.[index] || 0) * 100) }))); setExpectedModel(inputs.expected_return_model); setCovarianceModel(inputs.covariance_model); setObjective(inputs.objective); setSource({ kind: "saved_version", reference_id: versionId }); setReturnObservations(inputs.return_observations || null); setError(""); }
        catch (cause) { setError(cause?.message || "Portfolio version could not be loaded."); }
    };
    const compareVersions = async () => {
        if (!compareLeft || !compareRight || compareLeft === compareRight) { setError("Choose two different portfolio versions."); return; }
        try { const response = await studioRequest(`/portfolio/versions/${encodeURIComponent(compareLeft)}/compare/${encodeURIComponent(compareRight)}`); setComparison(response.comparison); setError(""); }
        catch (cause) { setError(cause?.message || "Portfolio versions could not be compared."); }
    };
    return <div className="flex min-h-0 flex-1 flex-col overflow-auto bg-[#050812] text-slate-200">
        <header className="flex min-h-14 items-center justify-between border-b border-white/10 px-6"><div><h2 className="text-sm font-semibold text-white">Portfolio construction</h2><p className="text-[10px] font-mono text-slate-500">Explicit assumptions · constrained allocation · reconciled implementation</p></div><div className="flex items-center gap-2"><button type="button" onClick={loadVersions} className="border border-white/10 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-slate-400 hover:text-white">Versions</button><button type="button" onClick={optimize} disabled={loading} className="bg-amber-400 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-black disabled:opacity-50">{loading ? "Optimizing…" : "Optimize"}</button></div></header>
        <div className="grid gap-0 xl:grid-cols-[minmax(560px,0.95fr)_minmax(520px,1.05fr)]">
            <section className="border-b border-white/10 p-6 xl:border-b-0 xl:border-r"><div className="mb-4 flex items-end justify-between"><div><h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-300">Investment set</h3><p className="mt-1 text-[10px] text-slate-500">Annualized user assumptions. Source: {source.kind.replaceAll('_', ' ')}.</p></div><div className="flex items-center gap-3"><label className="cursor-pointer text-[10px] text-slate-400 hover:text-white">Import holdings<input aria-label="Import holdings CSV" type="file" accept=".csv,text/csv" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; file.text().then((text) => { setAssets(parseHoldingsCsv(text)); setSource({ kind: "holdings_csv", reference_id: file.name }); setError(""); }).catch((cause) => setError(cause?.message || "Could not read holdings CSV.")); }} /></label><button type="button" onClick={() => { setAssets((current) => [...current, blankAsset()]); setSource({ kind: "manual" }); }} disabled={assets.length >= 50} className="text-[10px] text-slate-400 hover:text-white">+ Add asset</button></div></div>
                <nav aria-label="Portfolio input source" className="mb-4 flex border-y border-white/10 py-1">{[["assumptions", "Assumption model"], ["observations", "Return observations"]].map(([id, label]) => <button key={id} type="button" aria-pressed={inputMode === id} onClick={() => { setInputMode(id); if (id === "observations") { setExpectedModel("historical_mean"); setCovarianceModel("diagonal_shrinkage"); } }} className={`px-3 py-1.5 text-[9px] font-bold uppercase tracking-wider ${inputMode === id ? "bg-white/10 text-white" : "text-slate-600 hover:text-slate-300"}`}>{label}</button>)}</nav>
                {inputMode === "observations" ? <div className="mb-5 space-y-2"><div className="flex items-center justify-between"><label htmlFor="portfolio-return-csv" className="text-[9px] uppercase tracking-wider text-slate-500">CSV returns, decimal units</label><label className="cursor-pointer text-[9px] text-amber-300 hover:text-amber-200">Import CSV<input type="file" accept=".csv,text/csv" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; file.text().then((text) => { setReturnCsv(text); setSource({ kind: "returns_csv", reference_id: file.name }); }).catch(() => setError("Could not read return CSV.")); }} /></label></div><textarea id="portfolio-return-csv" value={returnCsv} onChange={(event) => setReturnCsv(event.target.value)} placeholder={'date,ASSET_A,ASSET_B\n2025-01-02,0.001,-0.002\n…'} className="h-28 w-full resize-y border border-white/10 bg-[#070b12] p-2 font-mono text-[10px] text-slate-300 outline-none focus:border-amber-400/50" /><button type="button" onClick={() => { try { const parsed = parseReturnCsv(returnCsv); setReturnObservations(parsed.observations); setAssets(parsed.assets.map((ticker, index) => ({ ticker, expected: "", volatility: "", current: index === 0 ? 100 : 0 }))); setSource((current) => current.kind === "returns_csv" ? current : { kind: "returns_csv", reference_id: "pasted" }); setError(""); } catch (cause) { setError(cause.message); } }} className="border border-white/10 px-3 py-1.5 text-[9px] uppercase tracking-wider text-slate-300 hover:border-amber-400/40">Apply observations</button>{returnObservations ? <span className="ml-3 text-[9px] text-emerald-300">{returnObservations.length} aligned rows loaded</span> : null}</div> : null}
                <div className="grid grid-cols-[1.1fr_repeat(3,0.8fr)_28px] border-b border-white/10 pb-2 text-[9px] uppercase tracking-wider text-slate-600"><span>Asset</span><span>Return %</span><span>Vol %</span><span>Current %</span><span /></div>
                {assets.map((asset, index) => <div key={index} className="grid grid-cols-[1.1fr_repeat(3,0.8fr)_28px] items-center border-b border-white/5 py-2">{["ticker", "expected", "volatility", "current"].map((field) => <input key={field} aria-label={`${field} ${index + 1}`} type={field === "ticker" ? "text" : "number"} value={asset[field]} onChange={(event) => updateAsset(index, field, event.target.value)} className="min-w-0 bg-transparent px-1 py-1 font-mono text-[11px] outline-none focus:bg-white/5" />)}<button type="button" aria-label={`Remove ${asset.ticker || `asset ${index + 1}`}`} disabled={assets.length <= 2} onClick={() => setAssets((current) => current.filter((_, assetIndex) => assetIndex !== index))} className="text-slate-600 hover:text-red-300 disabled:opacity-20">×</button></div>)}
                <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 text-[10px]"><label className="space-y-1 text-slate-500"><span className="block uppercase tracking-wider">Objective</span><select aria-label="Portfolio objective" value={objective} onChange={(event) => setObjective(event.target.value)} className="w-full border border-white/10 bg-[#090e18] px-2 py-2 text-slate-200"><option value="max_sharpe">Maximum Sharpe</option><option value="min_variance">Minimum variance</option><option value="max_return">Maximum return</option><option value="diversification">Diversification</option><option value="tracking_error">Minimum tracking error</option><option value="multi_objective">Risk / return trade-off</option></select></label><label className="space-y-1 text-slate-500"><span className="block uppercase tracking-wider">Expected return model</span><select aria-label="Expected return model" value={expectedModel} onChange={(event) => setExpectedModel(event.target.value)} className="w-full border border-white/10 bg-[#090e18] px-2 py-2 text-slate-200"><option value="supplied">Entered assumptions</option><option value="historical_mean">Historical mean</option><option value="zero">Zero / risk-only</option></select></label><label className="space-y-1 text-slate-500"><span className="block uppercase tracking-wider">Covariance model</span><select aria-label="Covariance model" value={covarianceModel} onChange={(event) => setCovarianceModel(event.target.value)} className="w-full border border-white/10 bg-[#090e18] px-2 py-2 text-slate-200"><option value="supplied">Volatility / correlation</option><option value="sample">Sample covariance</option><option value="diagonal_shrinkage">Diagonal shrinkage</option></select></label>{[["Common correlation", correlation, setCorrelation, -0.99, 0.99, 0.01], ["Shrinkage %", shrinkage, setShrinkage, 0, 100, 1], ["Periods per year", periodsPerYear, setPeriodsPerYear, 1, 366, 1], ["Minimum position %", minWeight, setMinWeight, -200, 100, 1], ["Maximum position %", maxWeight, setMaxWeight, -100, 200, 1], ["Gross leverage %", grossLeverage, setGrossLeverage, 100, 500, 1], ["Maximum turnover %", maxTurnover, setMaxTurnover, 0, 1000, 1], ["Target return %", targetReturn, setTargetReturn, -1000, 1000, 0.1], ["Risk aversion %", riskAversion, setRiskAversion, 0, 100, 1], ["One-way cost bps", costBps, setCostBps, 0, 1000, 1]].map(([label, value, setter, min, max, step]) => <label key={label} className="space-y-1 text-slate-500"><span className="block uppercase tracking-wider">{label}</span><input aria-label={label} type="number" min={min} max={max} step={step} value={value} onChange={(event) => setter(event.target.value)} className="w-full border border-white/10 bg-[#090e18] px-2 py-2 text-slate-200" /></label>)}</div>
                {covarianceModel === "supplied" ? <details className="mt-4 border-y border-white/10 py-2"><summary className="cursor-pointer text-[9px] uppercase tracking-wider text-slate-500">Advanced covariance matrix override</summary><textarea aria-label="Covariance matrix override" value={covarianceOverride} onChange={(event) => setCovarianceOverride(event.target.value)} placeholder="Optional JSON square matrix" className="mt-2 h-24 w-full border border-white/10 bg-[#070b12] p-2 font-mono text-[10px] text-slate-300" /></details> : null}
                <details className="border-b border-white/10 py-2"><summary className="cursor-pointer text-[9px] uppercase tracking-wider text-slate-500">Benchmark, exposures, and scenarios</summary><div className="mt-2 grid gap-2"><textarea aria-label="Benchmark weights" value={benchmarkWeights} onChange={(event) => setBenchmarkWeights(event.target.value)} placeholder="Benchmark weights JSON, ordered like assets: [0.6, 0.4]" className="h-16 w-full border border-white/10 bg-[#070b12] p-2 font-mono text-[10px] text-slate-300" /><textarea aria-label="Linear exposure constraints" value={linearConstraints} onChange={(event) => setLinearConstraints(event.target.value)} placeholder={'[{"name":"sector cap","coefficients":[1,0],"max":0.4}]'} className="h-20 w-full border border-white/10 bg-[#070b12] p-2 font-mono text-[10px] text-slate-300" /><textarea aria-label="Portfolio scenarios" value={scenarios} onChange={(event) => setScenarios(event.target.value)} placeholder={'[{"name":"equity selloff","shocks":[-0.2,0.03]}]'} className="h-20 w-full border border-white/10 bg-[#070b12] p-2 font-mono text-[10px] text-slate-300" /></div></details>
                <p className="mt-5 border-l border-amber-400/40 pl-3 text-[10px] leading-relaxed text-slate-500">All estimates come from entered assumptions, the supplied covariance matrix, or imported aligned returns according to the selected models. Net weight, position bounds, gross leverage, turnover, and optional target return are enforced; unavailable tax, liquidity, sector, and factor inputs remain explicit.</p>{error ? <div role="alert" className="mt-4 border-l-2 border-red-400 pl-3 text-[10px] text-red-300">{error}</div> : null}
            </section>
            <section className="p-6"><PortfolioAnalysis result={result} />{result ? <div className="mt-6 border-t border-white/10 pt-4"><h3 className="mb-3 text-[9px] font-bold uppercase tracking-wider text-slate-500">Version lifecycle</h3><div className="flex gap-2"><input aria-label="Portfolio version name" value={saveName} onChange={(event) => setSaveName(event.target.value)} maxLength={100} placeholder="Version name" className="min-w-0 flex-1 border border-white/10 bg-[#070b12] px-2 py-2 text-[10px] text-slate-200" /><button type="button" onClick={saveVersion} className="border border-amber-400/40 px-3 text-[9px] uppercase tracking-wider text-amber-300">Save immutable version</button></div>{versions.length ? <div className="mt-4"><div className="max-h-36 overflow-auto border-y border-white/10">{versions.map((version) => <button key={version.version_id} type="button" onClick={() => loadVersion(version.version_id)} className="grid w-full grid-cols-[1fr_150px] border-b border-white/5 px-2 py-2 text-left text-[9px] hover:bg-white/[0.03]"><span className="text-slate-300">{version.name}</span><span className="truncate text-right font-mono text-slate-600">{version.artifact_id}</span></button>)}</div><div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2"><select aria-label="Left portfolio version" value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)} className="border border-white/10 bg-[#070b12] p-2 text-[9px]"><option value="">Baseline version</option>{versions.map((version) => <option key={version.version_id} value={version.version_id}>{version.name}</option>)}</select><select aria-label="Right portfolio version" value={compareRight} onChange={(event) => setCompareRight(event.target.value)} className="border border-white/10 bg-[#070b12] p-2 text-[9px]"><option value="">Comparison version</option>{versions.map((version) => <option key={version.version_id} value={version.version_id}>{version.name}</option>)}</select><button type="button" onClick={compareVersions} className="border border-white/10 px-3 text-[9px] uppercase text-slate-300">Compare</button></div>{comparison ? <div className="mt-3 border-l border-amber-400/40 pl-3 font-mono text-[9px]"><div className="text-slate-300">{comparison.left.name} → {comparison.right.name}</div>{Object.entries(comparison.weight_delta).map(([asset, delta]) => <div key={asset} className="flex justify-between py-0.5 text-slate-500"><span>{asset}</span><span>{delta >= 0 ? "+" : ""}{percent(delta)}</span></div>)}</div> : null}</div> : null}</div> : null}</section>
        </div>
    </div>;
}
