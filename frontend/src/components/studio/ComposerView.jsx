"use client";

import React, { useEffect, useRef, useState } from "react";
import { studioRequest } from "@/lib/studioApi";
import { useStudioResultStore } from "@/stores/studio/resultStore";
import { useComposerSelectionStore } from "@/stores/studio/composerSelectionStore";

const blankBlock = (reference = null) => ({
    block_id: `block_${globalThis.crypto?.randomUUID?.() || Date.now()}`,
    kind: "artifact", title: "", reference, metric_paths: "", text: "", citations: "", layout: { w: 6, h: 4 },
});
const lines = (value) => String(value || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
const display = (value) => value == null ? "Unavailable" : typeof value === "object" ? JSON.stringify(value) : String(value);
const artifactKey = (reference) => reference?.type && reference?.id ? `${reference.type}:${reference.id}` : "";
const numericValues = (metrics) => Object.values(metrics || {}).filter((value) => typeof value === "number" && Number.isFinite(value));

function MetricSparkline({ blockId, values }) {
    const canvasRef = useRef(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || values.length === 0) return;
        let context = null;
        try { context = canvas.getContext("2d"); } catch { context = null; }
        if (!context) return;
        const width = canvas.width; const height = canvas.height;
        context.clearRect(0, 0, width, height);
        const max = Math.max(...values.map((value) => Math.abs(value)), 1e-9);
        const barWidth = width / values.length;
        values.forEach((value, index) => {
            const barHeight = Math.max(2, (Math.abs(value) / max) * (height - 8));
            context.fillStyle = value < 0 ? "#b3442c" : "#8a6d1c";
            context.fillRect(index * barWidth + 2, height - 4 - barHeight, barWidth - 4, barHeight);
        });
    }, [blockId, values]);
    if (values.length === 0) return null;
    return <canvas ref={canvasRef} id={`composer-chart-${blockId}`} width={320} height={64} aria-label="Metric chart" className="mt-3 w-full border border-[#172033]/10" />;
}

export default function ComposerView() {
    const portfolioVersion = useStudioResultStore((state) => state.portfolioVersion);
    const wfJob = useStudioResultStore((state) => state.wfJob);
    const selectedArtifact = useComposerSelectionStore((state) => state.selectedArtifact);
    const selectedMetric = useComposerSelectionStore((state) => state.selectedMetric);
    const setSelectedArtifact = useComposerSelectionStore((state) => state.setSelectedArtifact);
    const setSelectedMetric = useComposerSelectionStore((state) => state.setSelectedMetric);
    const defaultReference = portfolioVersion?.version_id ? { type: "portfolio_version", id: portfolioVersion.version_id }
        : wfJob?.job_id ? { type: "validation_job", id: wfJob.job_id } : null;
    const [recipeId, setRecipeId] = useState("");
    const [name, setName] = useState("");
    const [template, setTemplate] = useState("custom");
    const [blocks, setBlocks] = useState(() => [blankBlock(null)]);
    const [recipes, setRecipes] = useState([]);
    const [report, setReport] = useState(null);
    const [views, setViews] = useState([]);
    const [viewName, setViewName] = useState("");
    const [noteTitle, setNoteTitle] = useState("");
    const [noteContent, setNoteContent] = useState("");
    const [notes, setNotes] = useState([]);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    const refresh = async () => {
        const [recipeResponse, noteResponse] = await Promise.all([
            studioRequest("/reports/recipes"), studioRequest("/reports/notes"),
        ]);
        setRecipes(recipeResponse.recipes || []); setNotes(noteResponse.notes || []);
    };
    useEffect(() => { refresh().catch((cause) => setError(cause?.message || "Saved research outputs could not be loaded.")); }, []);
    useEffect(() => {
        if (!defaultReference) return;
        setBlocks((current) => current.map((block, index) => index === 0 && !block.reference ? { ...block, reference: defaultReference } : block));
    }, [defaultReference?.id, defaultReference?.type]); // eslint-disable-line react-hooks/exhaustive-deps

    const updateBlock = (index, patch) => setBlocks((current) => current.map((block, blockIndex) => blockIndex === index ? { ...block, ...patch } : block));
    const serializeBlocks = () => blocks.map((block) => ({
        ...block,
        reference: block.reference?.type && block.reference?.id ? block.reference : null,
        metric_paths: lines(block.metric_paths), citations: lines(block.citations),
        layout: { w: Number(block.layout.w), h: Number(block.layout.h) },
    }));
    const save = async () => {
        setBusy(true); setError("");
        try {
            const response = await studioRequest("/reports/recipes", { method: "POST", retries: 0, body: { recipe_id: recipeId || null, name: name.trim(), template, blocks: serializeBlocks() } });
            setRecipeId(response.recipe.recipe_id); await refresh();
            const rendered = await studioRequest(`/reports/recipes/${encodeURIComponent(response.recipe.recipe_id)}/render`);
            setReport(rendered.report); setViews(rendered.report?.views || response.recipe?.views || []);
        } catch (cause) { setError(cause?.message || "Output recipe could not be saved."); }
        finally { setBusy(false); }
    };
    const load = async (id) => {
        setBusy(true); setError("");
        try {
            const [saved, rendered] = await Promise.all([
                studioRequest(`/reports/recipes/${encodeURIComponent(id)}`),
                studioRequest(`/reports/recipes/${encodeURIComponent(id)}/render`),
            ]);
            const recipe = saved.recipe; setRecipeId(recipe.recipe_id); setName(recipe.name); setTemplate(recipe.template);
            setBlocks(recipe.blocks.map((block) => ({ ...block, metric_paths: (block.metric_paths || []).join("\n"), citations: (block.citations || []).join("\n") })));
            setReport(rendered.report); setViews(rendered.report?.views || recipe.views || []);
        } catch (cause) { setError(cause?.message || "Output recipe could not be opened."); }
        finally { setBusy(false); }
    };
    const applyTemplate = async () => {
        if (template === "custom") { setError("Select a report template before applying its layout."); return; }
        setBusy(true); setError("");
        try {
            const response = await studioRequest(`/reports/templates/${encodeURIComponent(template)}`);
            setBlocks((response.template.blocks || []).map((block) => ({
                ...block,
                reference: block.reference || (block.kind === "artifact" ? defaultReference : null),
                metric_paths: (block.metric_paths || []).join("\n"),
                citations: (block.citations || []).join("\n"),
            })));
        } catch (cause) { setError(cause?.message || "Report template could not be applied."); }
        finally { setBusy(false); }
    };
    const saveView = async () => {
        if (!recipeId) { setError("Save the recipe before saving a named view."); return; }
        if (!viewName.trim()) { setError("Name the view before saving it."); return; }
        setBusy(true); setError("");
        try {
            const layouts = Object.fromEntries(blocks.map((block) => [block.block_id, { w: Number(block.layout.w), h: Number(block.layout.h) }]));
            const response = await studioRequest(`/reports/recipes/${encodeURIComponent(recipeId)}/views`, { method: "POST", retries: 0, body: { name: viewName.trim(), layouts } });
            setViews(response.recipe?.views || []); setViewName("");
        } catch (cause) { setError(cause?.message || "Layout view could not be saved."); }
        finally { setBusy(false); }
    };
    const applyView = (view) => {
        setBlocks((current) => current.map((block) => view.layouts?.[block.block_id] ? { ...block, layout: { ...block.layout, ...view.layouts[block.block_id] } } : block));
    };
    const downloadPng = (blockId) => {
        try {
            const canvas = document.getElementById(`composer-chart-${blockId}`);
            const url = canvas?.toDataURL?.("image/png");
            if (!url || url === "data:,") { setError("No chart image is available for this block yet."); return; }
            const link = document.createElement("a");
            link.href = url; link.download = `${blockId}.png`; link.click();
        } catch { setError("Chart image export is unavailable in this browser."); }
    };
    const saveNote = async () => {
        const reference = defaultReference;
        if (!reference) { setError("Select or create an artifact before writing a linked note."); return; }
        setBusy(true); setError("");
        try {
            await studioRequest("/reports/notes", { method: "POST", retries: 0, body: { title: noteTitle.trim(), content: noteContent, reference } });
            setNoteTitle(""); setNoteContent(""); await refresh();
        } catch (cause) { setError(cause?.message || "Research note could not be saved."); }
        finally { setBusy(false); }
    };

    return <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#050812] text-slate-200">
        <style media="print">{`@media print { aside, header .no-print { display: none !important; } main { overflow: visible !important; background: #fff !important; } }`}</style>
        <header className="flex min-h-14 items-center justify-between border-b border-white/10 px-6"><div><h2 className="text-sm font-semibold text-white">Research output composer</h2><p className="font-mono text-[10px] text-slate-500">Reference-only layouts · live metric resolution · deterministic exports</p></div><div className="flex gap-2 no-print">{report ? ["html", "csv", "json", "arrow"].map((format) => <a key={format} href={`/api/studio/reports/recipes/${encodeURIComponent(recipeId)}/export/${format}`} className="border border-white/10 px-3 py-2 text-[9px] font-bold uppercase text-slate-300 hover:border-amber-400/40">{format}</a>) : null}<button type="button" onClick={() => window.print()} aria-label="Print or save PDF" className="border border-white/10 px-3 py-2 text-[9px] font-bold uppercase text-slate-300 hover:border-amber-400/40">PDF</button><button type="button" onClick={save} disabled={busy || !name.trim() || !blocks.length} className="bg-amber-400 px-4 py-2 text-[9px] font-bold uppercase text-black disabled:opacity-30">Save and render</button></div></header>
        {error ? <div role="alert" className="border-b border-red-400/20 bg-red-400/5 px-6 py-2 text-[10px] text-red-300">{error}</div> : null}
        {(report?.warnings || []).length > 0 ? <div role="status" className="border-b border-amber-400/20 bg-amber-400/5 px-6 py-2 text-[10px] text-amber-200">{report.warnings.map((item, index) => <div key={index}>{item.warning}</div>)}</div> : null}
        <div className="grid min-h-0 flex-1 grid-cols-[380px_minmax(0,1fr)_320px]">
            <aside className="overflow-auto border-r border-white/10 p-5"><div className="grid grid-cols-[1fr_140px] gap-2"><input aria-label="Output recipe name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Output name" className="h-8 border border-white/10 bg-[#080c14] px-2 text-[10px]" /><select aria-label="Report template" value={template} onChange={(event) => setTemplate(event.target.value)} className="h-8 border border-white/10 bg-[#080c14] px-2 text-[9px]"><option value="custom">Custom</option><option value="strategy_review">Strategy review</option><option value="validation">Validation</option><option value="portfolio_review">Portfolio review</option><option value="paper_reconciliation">Paper reconciliation</option></select></div>
                <button type="button" onClick={applyTemplate} disabled={busy || template === "custom"} aria-label="Apply template layout" className="mt-2 h-8 w-full border border-white/10 text-[8px] font-bold uppercase text-slate-400 hover:border-amber-400/40 disabled:opacity-30">Apply template layout</button>
                <div className="mt-3 border border-white/10 p-2"><div className="text-[8px] font-bold uppercase text-slate-500">Saved views</div><div className="mt-1 flex gap-2"><input aria-label="Saved view name" value={viewName} onChange={(event) => setViewName(event.target.value)} placeholder="View name" className="h-7 flex-1 border border-white/10 bg-[#080c14] px-2 text-[9px]" /><button type="button" onClick={saveView} disabled={busy || !recipeId} aria-label="Save layout view" className="h-7 border border-amber-400/40 px-2 text-[8px] font-bold uppercase text-amber-300 disabled:opacity-30">Save</button></div><div className="mt-1">{views.map((view) => <button key={view.view_id} type="button" onClick={() => applyView(view)} aria-label={`Apply view ${view.name}`} className="mt-1 w-full border border-white/5 px-2 py-1 text-left text-[9px] text-slate-300 hover:border-amber-400/40">{view.name}</button>)}</div></div>
                <div className="mt-4 space-y-3">{blocks.map((block, index) => <section key={block.block_id} className="border-t border-white/10 pt-3"><div className="flex items-center justify-between"><span className="font-mono text-[8px] text-amber-400">BLOCK {index + 1}</span><div className="flex gap-2"><button type="button" onClick={() => setSelectedArtifact(artifactKey(block.reference))} aria-label={`Link block ${index + 1} artifact`} className="text-[8px] uppercase text-slate-500 hover:text-amber-300">{selectedArtifact && selectedArtifact === artifactKey(block.reference) ? "Linked" : "Link"}</button><button type="button" onClick={() => setBlocks((current) => current.filter((_, itemIndex) => itemIndex !== index))} className="text-[8px] uppercase text-slate-600 hover:text-red-300">Remove</button></div></div><div className="mt-2 grid grid-cols-2 gap-2"><select aria-label={`Block ${index + 1} kind`} value={block.kind} onChange={(event) => updateBlock(index, { kind: event.target.value })} className="h-8 border border-white/10 bg-[#080c14] px-2 text-[9px]"><option value="artifact">Artifact</option><option value="narrative">Narrative</option><option value="note">Note</option></select><input aria-label={`Block ${index + 1} title`} value={block.title} onChange={(event) => updateBlock(index, { title: event.target.value })} placeholder="Block title" className="h-8 border border-white/10 bg-[#080c14] px-2 text-[9px]" /></div><div className="mt-2 grid grid-cols-[130px_1fr] gap-2"><select aria-label={`Block ${index + 1} reference type`} value={block.reference?.type || ""} onChange={(event) => updateBlock(index, { reference: { type: event.target.value, id: block.reference?.id || "" } })} className="h-8 border border-white/10 bg-[#080c14] px-2 text-[8px]"><option value="">No reference</option><option value="portfolio_version">Portfolio version</option><option value="validation_job">Validation job</option><option value="paper_deployment">Paper deployment</option><option value="paper_event">Paper event</option><option value="research_note">Research note</option></select><input aria-label={`Block ${index + 1} reference id`} value={block.reference?.id || ""} onChange={(event) => updateBlock(index, { reference: { type: block.reference?.type || "", id: event.target.value } })} placeholder="Artifact ID" className="h-8 border border-white/10 bg-[#080c14] px-2 font-mono text-[8px]" /></div><textarea aria-label={`Block ${index + 1} metric paths`} value={block.metric_paths} onChange={(event) => updateBlock(index, { metric_paths: event.target.value })} placeholder="Metric paths, one per line" className="mt-2 h-16 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[8px]" /><textarea aria-label={`Block ${index + 1} narrative`} value={block.text} onChange={(event) => updateBlock(index, { text: event.target.value })} placeholder="Narrative or annotation" className="mt-2 h-16 w-full resize-y border border-white/10 bg-[#080c14] p-2 text-[9px]" /><div className="mt-2 flex items-center gap-2 text-[8px] uppercase text-slate-600">Width<input aria-label={`Block ${index + 1} width`} type="number" min="1" max="12" value={block.layout.w} onChange={(event) => updateBlock(index, { layout: { ...block.layout, w: event.target.value } })} onKeyDown={(event) => { if (event.key === "ArrowUp" || event.key === "ArrowDown") { event.preventDefault(); updateBlock(index, { layout: { ...block.layout, w: Math.min(12, Math.max(1, Number(block.layout.w || 1) + (event.key === "ArrowUp" ? 1 : -1))) } }); } }} className="h-7 w-12 border border-white/10 bg-[#080c14] px-1" />Height<input aria-label={`Block ${index + 1} height`} type="number" min="1" max="24" value={block.layout.h} onChange={(event) => updateBlock(index, { layout: { ...block.layout, h: event.target.value } })} onKeyDown={(event) => { if (event.key === "ArrowUp" || event.key === "ArrowDown") { event.preventDefault(); updateBlock(index, { layout: { ...block.layout, h: Math.min(24, Math.max(1, Number(block.layout.h || 1) + (event.key === "ArrowUp" ? 1 : -1))) } }); } }} className="h-7 w-12 border border-white/10 bg-[#080c14] px-1" /></div></section>)}</div><button type="button" onClick={() => setBlocks((current) => [...current, blankBlock(defaultReference)])} className="mt-4 w-full border border-dashed border-white/15 py-2 text-[8px] uppercase text-slate-500 hover:border-amber-400/40">Add block</button>
            </aside>
            <main className="overflow-auto bg-[#f2f0e9] p-8 text-[#172033]"><div className="mx-auto max-w-4xl"><div className="border-b border-[#172033]/20 pb-5"><span className="font-mono text-[9px] uppercase tracking-[0.22em] text-[#6d6658]">{report?.template || "Unrendered recipe"}</span><h1 className="mt-2 font-serif text-3xl">{report?.name || name || "Untitled output"}</h1>{report ? <div className="mt-2 break-all font-mono text-[8px] text-[#777164]">Report {report.report_hash}{report.export_version ? ` · v${report.export_version}` : ""}{report.engine_version ? ` · ${report.engine_version}` : ""}</div> : null}</div><div className="mt-5 grid grid-cols-12 gap-4">{report?.blocks?.map((block) => { const linked = selectedArtifact && artifactKey(block.resolved?.reference) === selectedArtifact; return <section key={block.block_id} data-linked={linked ? "true" : "false"} style={{ gridColumn: `span ${Math.min(12, Math.max(1, Number(block.layout?.w) || 12))}`, outline: linked ? "2px solid #b98a0c" : "none" }} className="border-t border-[#172033]/25 pt-3"><h2 className="font-serif text-lg">{block.title || block.kind}</h2>{block.text ? <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{block.text}</p> : null}<MetricSparkline blockId={block.block_id} values={numericValues(block.resolved?.metrics)} /><dl className="mt-3">{Object.entries(block.resolved?.metrics || {}).map(([path, value]) => <div key={path} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 border-b border-[#172033]/10 py-2 text-xs" style={{ background: selectedMetric === path ? "#f5e6b8" : "transparent" }}><dt className="font-mono text-[9px] text-[#6d6658]"><button type="button" onClick={() => setSelectedMetric(path)} aria-label={`Highlight metric ${path}`} className="text-left underline decoration-dotted">{path}</button>{(block.resolved?.formulas?.[path] || report?.formulas?.[path]) ? <div className="mt-1 font-mono text-[8px] text-[#918a7c]">{block.resolved?.formulas?.[path] || report?.formulas?.[path]}</div> : null}</dt><dd className="max-w-sm break-words text-right">{display(value)}</dd></div>)}</dl><div className="mt-3 flex items-center justify-between gap-2"><div className="break-all font-mono text-[7px] text-[#918a7c]">{display(block.resolved?.reference)} · {block.resolved?.artifact_hash}</div>{numericValues(block.resolved?.metrics).length > 0 ? <button type="button" onClick={() => downloadPng(block.block_id)} aria-label={`Download chart PNG for ${block.title || block.kind}`} className="no-print shrink-0 border border-[#172033]/20 px-2 py-1 text-[8px] font-bold uppercase">PNG</button> : null}</div></section>; })}</div>{!report ? <div className="py-32 text-center font-serif text-lg text-[#918a7c]">Save the recipe to resolve its referenced evidence.</div> : null}</div></main>
            <aside className="overflow-auto border-l border-white/10 p-5"><h3 className="text-[9px] font-bold uppercase tracking-wider text-amber-400">Saved outputs</h3><div className="mt-2 border-y border-white/10">{recipes.map((recipe) => <button key={recipe.recipe_id} type="button" onClick={() => load(recipe.recipe_id)} className="w-full border-b border-white/5 px-2 py-2 text-left"><div className="text-[9px] text-slate-300">{recipe.name}</div><div className="mt-1 font-mono text-[8px] text-slate-700">{recipe.recipe_id}</div></button>)}</div><h3 className="mt-7 text-[9px] font-bold uppercase tracking-wider text-slate-500">Artifact-linked note</h3><input aria-label="Research note title" value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} placeholder="Decision title" className="mt-2 h-8 w-full border border-white/10 bg-[#080c14] px-2 text-[9px]" /><textarea aria-label="Research note content" value={noteContent} onChange={(event) => setNoteContent(event.target.value)} placeholder="Evidence, decision, and follow-up" className="mt-2 h-28 w-full resize-y border border-white/10 bg-[#080c14] p-2 text-[9px]" /><button type="button" onClick={saveNote} disabled={busy || !noteTitle.trim()} className="mt-2 h-8 w-full border border-amber-400/40 text-[8px] font-bold uppercase text-amber-300 disabled:opacity-30">Save linked note</button><div className="mt-4 border-y border-white/10">{notes.map((note) => <div key={note.note_id} className="border-b border-white/5 py-2"><div className="text-[9px] text-slate-300">{note.title}</div><div className="mt-1 line-clamp-3 text-[8px] leading-4 text-slate-600">{note.content}</div><div className="mt-1 truncate font-mono text-[7px] text-slate-700">{note.reference?.type}:{note.reference?.id}</div></div>)}</div></aside>
        </div>
    </div>;
}
