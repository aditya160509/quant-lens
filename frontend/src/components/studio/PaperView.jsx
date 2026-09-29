"use client";

import React, { useEffect, useMemo, useState } from "react";
import { studioRequest } from "@/lib/studioApi";
import { useStudioResultStore } from "@/stores/studio/resultStore";

const eventTypes = ["signal", "intended_order", "submitted_order", "fill", "position", "valuation", "alert"];
const shown = (value) => value == null || value === "" ? "Unavailable" : String(value);

export default function PaperView() {
    const portfolioVersion = useStudioResultStore((state) => state.portfolioVersion);
    const portfolioArtifact = useStudioResultStore((state) => state.portfolioArtifact);
    const wfJob = useStudioResultStore((state) => state.wfJob);
    const promotionRecords = useStudioResultStore((state) => state.promotionAuditRecords);
    const promotion = [...promotionRecords].reverse().find((record) => record.action === "promote" && record.job_id === wfJob?.job_id);
    const [deployments, setDeployments] = useState([]);
    const [selectedId, setSelectedId] = useState("");
    const [deployment, setDeployment] = useState(null);
    const [events, setEvents] = useState([]);
    const [reconciliation, setReconciliation] = useState(null);
    const [name, setName] = useState("");
    const [universe, setUniverse] = useState("");
    const [schedule, setSchedule] = useState('{"kind":"manual"}');
    const [limits, setLimits] = useState("{}");
    const [eventType, setEventType] = useState("signal");
    const [eventPayload, setEventPayload] = useState("{}");
    const [parentEventId, setParentEventId] = useState("");
    const [actor, setActor] = useState("");
    const [reason, setReason] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const eligible = Boolean(portfolioVersion?.version_id && portfolioArtifact?.artifact_id && wfJob?.status === "completed" && promotion);

    const loadDeployments = async () => {
        const response = await studioRequest("/paper/deployments");
        setDeployments(response.deployments || []);
        if (!selectedId && response.deployments?.length) setSelectedId(response.deployments[0].deployment_id);
    };
    const loadSelected = async (deploymentId = selectedId) => {
        if (!deploymentId) { setDeployment(null); setEvents([]); setReconciliation(null); return; }
        const [detail, ledger, recon] = await Promise.all([
            studioRequest(`/paper/deployments/${encodeURIComponent(deploymentId)}`),
            studioRequest(`/paper/deployments/${encodeURIComponent(deploymentId)}/events`),
            studioRequest(`/paper/deployments/${encodeURIComponent(deploymentId)}/reconciliation`),
        ]);
        setDeployment(detail.deployment); setEvents(ledger.events || []); setReconciliation(recon.reconciliation);
    };
    useEffect(() => { loadDeployments().catch((cause) => setError(cause?.message || "Paper deployments could not be loaded.")); }, []); // eslint-disable-line react-hooks/exhaustive-deps
    useEffect(() => { loadSelected().catch((cause) => setError(cause?.message || "Paper deployment could not be loaded.")); }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

    const parentOptions = useMemo(() => events.filter((event) => {
        const expected = { intended_order: "signal", submitted_order: "intended_order", fill: "submitted_order", position: "fill" }[eventType];
        return expected && event.event_type === expected;
    }), [eventType, events]);

    const createDeployment = async () => {
        if (!eligible) { setError("Save the portfolio version, complete its validation, and record a promote decision first."); return; }
        setBusy(true); setError("");
        try {
            const parsedSchedule = JSON.parse(schedule);
            const parsedLimits = JSON.parse(limits);
            const response = await studioRequest("/paper/deployments", { method: "POST", retries: 0, body: {
                name: name.trim(), source_version_id: portfolioVersion.version_id,
                validation_job_id: wfJob.job_id, promotion_audit_id: promotion.audit_id,
                schedule: parsedSchedule,
                universe: universe.split(",").map((value) => value.trim()).filter(Boolean),
                limits: parsedLimits,
            } });
            await loadDeployments(); setSelectedId(response.deployment.deployment_id); setName("");
        } catch (cause) { setError(cause?.message || "Paper deployment could not be created."); }
        finally { setBusy(false); }
    };
    const appendEvent = async () => {
        if (!selectedId) return;
        setBusy(true); setError("");
        try {
            const response = await studioRequest(`/paper/deployments/${encodeURIComponent(selectedId)}/events`, { method: "POST", retries: 0, body: {
                event_type: eventType, payload: JSON.parse(eventPayload), parent_event_id: parentEventId || null,
            } });
            setParentEventId(""); setEventPayload("{}"); await loadSelected();
            return response.event;
        } catch (cause) { setError(cause?.message || "Paper event could not be recorded."); await loadSelected().catch(() => {}); }
        finally { setBusy(false); }
    };
    const toggleKillSwitch = async (engaged) => {
        if (!actor.trim() || !reason.trim()) { setError("Actor and reason are required for kill-switch changes."); return; }
        setBusy(true); setError("");
        try {
            await studioRequest(`/paper/deployments/${encodeURIComponent(selectedId)}/kill-switch`, { method: "POST", retries: 0, body: { engaged, actor: actor.trim(), reason: reason.trim() } });
            setReason(""); await loadSelected();
        } catch (cause) { setError(cause?.message || "Kill switch could not be changed."); }
        finally { setBusy(false); }
    };

    return <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#050812] text-slate-200">
        <header className="flex min-h-14 items-center justify-between border-b border-white/10 px-6"><div><h2 className="text-sm font-semibold text-white">Paper execution</h2><p className="font-mono text-[10px] text-slate-500">Promoted artifact · causal ledger · reconciliation · operator controls</p></div><div className="font-mono text-[9px] text-slate-500">{deployment ? `${deployment.deployment_id} · ${deployment.state}` : "No deployment selected"}</div></header>
        {error ? <div role="alert" className="border-b border-red-400/20 bg-red-400/5 px-6 py-2 text-[10px] text-red-300">{error}</div> : null}
        <div className="grid min-h-0 flex-1 grid-cols-[340px_minmax(0,1fr)_360px]">
            <aside className="overflow-auto border-r border-white/10 p-5">
                <h3 className="text-[9px] font-bold uppercase tracking-wider text-amber-400">Deployment contract</h3>
                <dl className="mt-3 space-y-1 border-y border-white/10 py-3 font-mono text-[9px]"><div className="flex justify-between"><dt className="text-slate-600">Version</dt><dd className="max-w-44 truncate text-slate-300">{shown(portfolioVersion?.version_id)}</dd></div><div className="flex justify-between"><dt className="text-slate-600">Artifact</dt><dd className="max-w-44 truncate text-slate-300">{shown(portfolioArtifact?.artifact_id)}</dd></div><div className="flex justify-between"><dt className="text-slate-600">Validation</dt><dd className="text-slate-300">{shown(wfJob?.job_id)}</dd></div><div className="flex justify-between"><dt className="text-slate-600">Promotion</dt><dd className="text-slate-300">{shown(promotion?.audit_id)}</dd></div></dl>
                <div className="mt-4 space-y-2"><input aria-label="Paper deployment name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Deployment name" className="h-8 w-full border border-white/10 bg-[#080c14] px-2 text-[10px]" /><input aria-label="Paper universe" value={universe} onChange={(event) => setUniverse(event.target.value)} placeholder="Comma-separated universe" className="h-8 w-full border border-white/10 bg-[#080c14] px-2 text-[10px]" /><label className="block text-[8px] uppercase text-slate-600">Schedule JSON<textarea value={schedule} onChange={(event) => setSchedule(event.target.value)} className="mt-1 h-16 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[9px] text-slate-300" /></label><label className="block text-[8px] uppercase text-slate-600">Limits JSON<textarea value={limits} onChange={(event) => setLimits(event.target.value)} className="mt-1 h-24 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[9px] text-slate-300" /></label><button type="button" disabled={busy || !eligible || !name.trim() || !universe.trim()} onClick={createDeployment} className="h-8 w-full bg-amber-400 text-[9px] font-bold uppercase text-black disabled:opacity-30">Create armed deployment</button>{!eligible ? <p className="text-[9px] leading-relaxed text-slate-600">Requires the exact saved portfolio version, completed passing validation, and promote record.</p> : null}</div>
                <h3 className="mt-7 text-[9px] font-bold uppercase tracking-wider text-slate-500">Durable deployments</h3><div className="mt-2 border-y border-white/10">{deployments.map((item) => <button key={item.deployment_id} type="button" onClick={() => setSelectedId(item.deployment_id)} className={`w-full border-b border-white/5 px-2 py-2 text-left text-[9px] ${selectedId === item.deployment_id ? "bg-amber-400/[0.07] text-white" : "text-slate-500"}`}><div className="flex justify-between"><span>{item.name}</span><span className={item.kill_switch?.engaged ? "text-red-300" : "text-emerald-300"}>{item.state}</span></div><div className="mt-1 truncate font-mono text-slate-700">{item.source_artifact_id}</div></button>)}</div>
            </aside>
            <main className="min-w-0 overflow-auto p-5">
                <div className="flex items-end justify-between"><div><h3 className="text-[9px] font-bold uppercase tracking-wider text-amber-400">Event ledger</h3><p className="mt-1 text-[9px] text-slate-600">Events are accepted as supplied. Nothing here simulates a broker fill.</p></div><span className="font-mono text-[9px] text-slate-600">{events.length} recorded</span></div>
                <div className="mt-3 grid grid-cols-[46px_112px_150px_1fr] border-y border-white/10 py-2 text-[8px] uppercase text-slate-600"><span>Seq</span><span>Type</span><span>Parent</span><span>Payload</span></div>{events.map((event) => <div key={event.event_id} className="grid grid-cols-[46px_112px_150px_1fr] border-b border-white/5 py-2 font-mono text-[9px]"><span className="text-slate-600">{event.sequence}</span><span className={event.event_type === "alert" ? "text-red-300" : "text-amber-300"}>{event.event_type}</span><span className="truncate text-slate-600">{event.parent_event_id || "root"}</span><span className="break-all text-slate-400">{JSON.stringify(event.payload)}</span></div>)}{!events.length ? <div className="py-20 text-center text-[10px] text-slate-700">No paper events recorded.</div> : null}
            </main>
            <aside className="overflow-auto border-l border-white/10 p-5">
                <h3 className="text-[9px] font-bold uppercase tracking-wider text-amber-400">Record observed event</h3><div className="mt-3 space-y-2"><select aria-label="Paper event type" value={eventType} onChange={(event) => { setEventType(event.target.value); setParentEventId(""); }} disabled={!deployment} className="h-8 w-full border border-white/10 bg-[#080c14] px-2 text-[10px]">{eventTypes.map((type) => <option key={type}>{type}</option>)}</select>{parentOptions.length ? <select aria-label="Parent paper event" value={parentEventId} onChange={(event) => setParentEventId(event.target.value)} className="h-8 w-full border border-white/10 bg-[#080c14] px-2 text-[9px]"><option value="">Select required parent</option>{parentOptions.map((event) => <option key={event.event_id} value={event.event_id}>{event.sequence} · {event.event_id}</option>)}</select> : null}<textarea aria-label="Paper event payload" value={eventPayload} onChange={(event) => setEventPayload(event.target.value)} className="h-32 w-full resize-y border border-white/10 bg-[#080c14] p-2 font-mono text-[9px] text-slate-300" /><button type="button" onClick={appendEvent} disabled={busy || !deployment} className="h-8 w-full border border-amber-400/40 text-[9px] font-bold uppercase text-amber-300 disabled:opacity-30">Append event</button></div>
                <h3 className="mt-7 text-[9px] font-bold uppercase tracking-wider text-slate-500">Reconciliation</h3><dl className="mt-2 border-y border-white/10 py-2 font-mono text-[9px]"><div className="flex justify-between"><dt className="text-slate-600">Fills</dt><dd>{shown(reconciliation?.summary?.fill_count)}</dd></div><div className="flex justify-between"><dt className="text-slate-600">Classified</dt><dd>{shown(reconciliation?.summary?.classified_fill_count)}</dd></div><div className="flex justify-between"><dt className="text-slate-600">Mean slippage</dt><dd>{reconciliation?.summary?.mean_slippage_bps == null ? "Unavailable" : `${reconciliation.summary.mean_slippage_bps.toFixed(2)} bps`}</dd></div><div className="flex justify-between"><dt className="text-slate-600">Alerts</dt><dd>{shown(reconciliation?.summary?.alert_count)}</dd></div></dl>
                {reconciliation?.fills?.length ? <div className="mt-2 border-y border-white/5">{reconciliation.fills.map((fill) => <div key={fill.fill_event_id} className="grid grid-cols-[1fr_auto] gap-2 border-b border-white/5 py-2 font-mono text-[8px]"><span className="truncate text-slate-500">{fill.fill_event_id}</span><span className={fill.classification === "adverse" ? "text-red-300" : fill.classification === "favorable" ? "text-emerald-300" : "text-slate-300"}>{fill.classification} · {fill.slippage_bps == null ? "unclassified" : `${fill.slippage_bps.toFixed(2)} bps`}</span></div>)}</div> : null}
                <h3 className="mt-7 text-[9px] font-bold uppercase tracking-wider text-slate-500">Kill switch</h3><div className={`mt-2 border-l-2 pl-3 text-[9px] ${deployment?.kill_switch?.engaged ? "border-red-400 text-red-300" : "border-emerald-400/40 text-slate-500"}`}>{deployment?.kill_switch?.engaged ? `Engaged: ${deployment.kill_switch.reason}` : "Not engaged"}</div><div className="mt-3 space-y-2"><input aria-label="Kill switch actor" value={actor} onChange={(event) => setActor(event.target.value)} placeholder="Operator" className="h-8 w-full border border-white/10 bg-[#080c14] px-2 text-[10px]" /><textarea aria-label="Kill switch reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required reason" className="h-16 w-full border border-white/10 bg-[#080c14] p-2 text-[9px]" /><div className="grid grid-cols-2 gap-2"><button type="button" disabled={busy || !deployment || deployment.kill_switch?.engaged} onClick={() => toggleKillSwitch(true)} className="h-8 border border-red-400/30 text-[9px] uppercase text-red-300 disabled:opacity-30">Engage</button><button type="button" disabled={busy || !deployment || !deployment.kill_switch?.engaged} onClick={() => toggleKillSwitch(false)} className="h-8 border border-white/10 text-[9px] uppercase text-slate-300 disabled:opacity-30">Release</button></div></div>
            </aside>
        </div>
    </div>;
}
