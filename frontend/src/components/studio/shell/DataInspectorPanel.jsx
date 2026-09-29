"use client";

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Database, X } from 'lucide-react';
import { useDataStudio } from '@/hooks/studio/useDataStudio';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';

const shown = (value) => value === null || value === undefined || value === '' ? 'Not reported' : String(value);

function VirtualDataPreview({ rows }) {
    const scrollRef = useRef(null);
    // eslint-disable-next-line react-hooks/incompatible-library -- the virtualizer owns the visible-row viewport
    const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => scrollRef.current, estimateSize: () => 27, overscan: 6 });
    return <div ref={scrollRef} className="h-44 overflow-auto border border-white/10" role="table" aria-label="Virtualized dataset preview"><div className="sticky top-0 z-10 grid grid-cols-3 bg-[#0c111b] px-1 py-1 text-[9px] text-slate-400" role="row"><span role="columnheader">Date</span><span role="columnheader" className="text-right">Close</span><span role="columnheader" className="text-right">Volume</span></div><div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>{virtualizer.getVirtualItems().map((item) => { const row = rows[item.index]; return <div key={`${row.date}-${item.index}`} role="row" className="absolute left-0 top-0 grid w-full grid-cols-3 border-t border-white/5 px-1 text-[9px] text-slate-300" style={{ height: item.size, transform: `translateY(${item.start}px)` }}><span role="cell">{shown(row.date)}</span><span role="cell" className="text-right">{shown(row.close)}</span><span role="cell" className="text-right">{shown(row.volume)}</span></div>; })}</div></div>;
}

export default function DataInspectorPanel({ onClose }) {
    const data = useStudioResultStore((state) => state.data);
    const ticker = useStudioWorkspaceStore((state) => state.ticker);
    const quality = data.metadata?.data_quality;
    const { cancel, deleteUpload, loadCatalog, loadFreshness, loadManifests, loadSeries, loadUploads, uploadDataset } = useDataStudio();
    const [catalog, setCatalog] = useState([]);
    const [freshness, setFreshness] = useState([]);
    const [manifests, setManifests] = useState([]);
    const [uploads, setUploads] = useState([]);
    const [query, setQuery] = useState('');
    const [preview, setPreview] = useState(null);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [uploadStatus, setUploadStatus] = useState('');
    useEffect(() => {
        let active = true;
        Promise.all([loadCatalog(), loadFreshness(), loadManifests(), loadUploads()])
            .then(([nextCatalog, nextFreshness, nextManifest, nextUploads]) => {
                if (!active) return;
                setCatalog(Array.isArray(nextCatalog) ? nextCatalog : []);
                setFreshness(Array.isArray(nextFreshness) ? nextFreshness : []);
                setManifests(Array.isArray(nextManifest?.datasets) ? nextManifest.datasets : []);
                setUploads(Array.isArray(nextUploads?.uploads) ? nextUploads.uploads : []);
            })
            .catch((cause) => active && setError(cause?.message || 'Data inventory unavailable'))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, [loadCatalog, loadFreshness, loadManifests, loadUploads]);
    const visibleCatalog = useMemo(() => {
        const needle = query.trim().toLowerCase();
        return catalog.filter((entry) => !needle || JSON.stringify(entry).toLowerCase().includes(needle));
    }, [catalog, query]);
    const freshnessByName = useMemo(() => Object.fromEntries(freshness.map((entry) => [entry.source_name, entry])), [freshness]);
    const summary = useMemo(() => {
        const candles = data.candles || [];
        const fields = candles[0] ? Object.keys(candles[0]) : [];
        const missing = candles.reduce((count, candle) => count + fields.filter((field) => candle[field] === null || candle[field] === undefined || (typeof candle[field] === 'number' && !Number.isFinite(candle[field]))).length, 0);
        return { fields: fields.map((field) => `${field}: ${typeof candles[0][field]}`), first: candles[0]?.time, last: candles.at(-1)?.time, missing };
    }, [data.candles]);

    return (
        <aside id="studio-data-inspector" aria-label="Data inspector" className="absolute inset-y-0 left-0 z-[70] w-[380px] overflow-auto border-r border-white/10 bg-[#080b12] shadow-2xl">
            <header className="sticky top-0 flex h-12 items-center justify-between border-b border-white/10 bg-[#0c111b] px-4">
                <div className="flex items-center gap-2"><Database size={15} className="text-amber-400" /><div><div className="text-[10px] font-bold uppercase tracking-widest text-white">Data inspector</div><div className="text-[9px] font-mono text-slate-500">{ticker} · current workspace artifact</div></div></div>
                <button aria-label="Close data inspector" onClick={onClose} className="rounded p-1.5 text-slate-500 hover:bg-white/5 hover:text-white"><X size={15} /></button>
            </header>
            <div className="space-y-5 p-4 font-mono">
                <section>
                    <h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Dataset catalog</h3>
                    <label className="sr-only" htmlFor="studio-data-search">Search datasets</label>
                    <input id="studio-data-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search source or type" className="mb-2 w-full border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-slate-200 outline-none focus:border-amber-400/60" />
                    {loading ? <div role="status" className="text-[10px] text-slate-500">Loading governed inventory…</div> : null}
                    {error ? <div role="alert" className="border-l-2 border-red-400 pl-2 text-[10px] text-red-300">{error}</div> : null}
                    <div className="max-h-48 space-y-1 overflow-auto" aria-label="Dataset catalog results">
                        {visibleCatalog.map((entry) => { const status = freshnessByName[entry.name]; return <button key={entry.name} type="button" onClick={() => { if (entry.name !== 'market_universe') return; setPreviewLoading(true); setError(''); loadSeries(ticker, { force: true, query: { limit: 100 } }).then(setPreview).catch((cause) => setError(cause?.message || 'Preview unavailable')).finally(() => setPreviewLoading(false)); }} className="block w-full border-l border-white/10 px-2 py-2 text-left hover:border-amber-400 hover:bg-white/[0.03]">
                            <span className="block text-[10px] text-slate-200">{entry.name}</span>
                            <span className="block text-[9px] text-slate-500">{entry.source_type} · {entry.update_frequency || 'frequency not reported'} · {status?.status || 'freshness unavailable'}</span>
                            {status?.data_as_of ? <span className="block text-[9px] text-slate-600">as of {status.data_as_of} · lag {shown(status.lag_trading_days)} trading days</span> : null}
                        </button>; })}
                    </div>
                </section>
                {previewLoading ? <section className="flex items-center justify-between text-[9px] text-slate-400"><span role="status">Loading bounded preview…</span><button type="button" onClick={() => cancel(`data.series.${ticker}`)} className="text-amber-300 hover:text-amber-200">Cancel preview</button></section> : null}
                {preview ? <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Bounded preview</h3><div className="mb-2 text-[9px] text-slate-500">{preview.count} of {preview.total_count} rows · server limit {preview.limit}{preview.truncated ? ' · truncated' : ''}</div><VirtualDataPreview rows={preview.series || []} /></section> : null}
                <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Governed upload</h3><form className="space-y-2" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const file = form.get('dataset'); if (!(file instanceof File) || !file.size) { setUploadStatus('Choose a CSV, JSON, or Parquet file.'); return; } setUploadStatus('Scanning and validating upload…'); uploadDataset(file, { sourceName: form.get('sourceName'), dateColumn: form.get('dateColumn'), symbolColumn: form.get('symbolColumn'), licenseStatus: form.get('licenseStatus'), permittedUseAttested: form.get('permittedUseAttested') === 'on', retentionDays: form.get('retentionDays') }).then((result) => { setUploadStatus(`Uploaded ${result.source_name}: ${result.validation_report?.rows ?? 'unknown'} rows · scan ${result.governance?.malware_scan?.status || 'not reported'}.`); return loadUploads(); }).then((next) => setUploads(next.uploads || [])).catch((cause) => setUploadStatus(cause?.message || 'Upload failed validation.')); }}>
                    <input name="sourceName" required maxLength={100} placeholder="Dataset name" aria-label="Dataset name" className="w-full border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-slate-200" />
                    <div className="grid grid-cols-2 gap-2"><input name="dateColumn" required maxLength={128} placeholder="Date column" aria-label="Date column" className="border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-slate-200" /><input name="symbolColumn" required maxLength={128} placeholder="Symbol column" aria-label="Symbol column" className="border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-slate-200" /></div>
                    <input name="dataset" type="file" required accept=".csv,.json,.parquet" aria-label="Dataset file" className="block w-full text-[9px] text-slate-500 file:mr-2 file:border-0 file:bg-white/10 file:px-2 file:py-1 file:text-slate-300" />
                    <div className="grid grid-cols-2 gap-2"><input name="licenseStatus" required maxLength={100} defaultValue="user-provided" aria-label="License status" className="border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-slate-200" /><input name="retentionDays" type="number" required min={1} max={3650} defaultValue={90} aria-label="Retention days" className="border border-white/10 bg-black/20 px-2 py-1.5 text-[10px] text-slate-200" /></div>
                    <label className="flex gap-2 text-[9px] leading-relaxed text-slate-400"><input name="permittedUseAttested" type="checkbox" required className="accent-amber-400" />I confirm I have permission to use and store this dataset.</label>
                    <button type="submit" className="border border-amber-400/40 px-2 py-1 text-[9px] uppercase tracking-wider text-amber-300 hover:bg-amber-400/10">Upload and validate</button>
                    {uploadStatus ? <div role="status" className="text-[9px] text-slate-400">{uploadStatus}</div> : null}
                    <p className="text-[9px] leading-relaxed text-slate-600">Private to the authenticated owner. Server limits: 25 MB, 1,000,000 rows, 256 columns. The built-in scan rejects EICAR and executable file signatures, then format decoders validate content. It is not a general antivirus engine. Expired uploads are removed on inventory access and may be deleted immediately below.</p>
                </form></section>
                {uploads.length ? <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Private uploads</h3><div className="space-y-2">{uploads.map((entry) => <div key={entry.upload_id} className="border-l border-white/10 pl-2 text-[9px]"><div className="flex items-center justify-between gap-2"><span className="text-slate-200">{entry.source_name}</span><button type="button" className="text-red-300 hover:text-red-200" onClick={() => { if (!window.confirm(`Delete ${entry.source_name}? This cannot be undone.`)) return; deleteUpload(entry.upload_id).then(() => { setUploads((current) => current.filter((item) => item.upload_id !== entry.upload_id)); setUploadStatus(`Deleted ${entry.source_name}.`); }).catch((cause) => setUploadStatus(cause?.message || 'Delete failed.')); }}>Delete</button></div><div className="text-slate-600">expires {shown(entry.expires_at)} · {shown(entry.governance?.license_status)}</div></div>)}</div></section> : null}
                <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Validated manifests</h3><div className="max-h-52 space-y-2 overflow-auto">{manifests.map((entry) => <details key={entry.id} className="border-l border-white/10 pl-2 text-[9px]"><summary className="cursor-pointer text-slate-200">{entry.id} · {entry.status}</summary><dl className="mt-2 space-y-1 text-slate-500"><div>coverage: {shown(entry.date_min)} to {shown(entry.date_max)}</div><div>rows: {shown(entry.rows)} · format: {shown(entry.format)}</div><div>path: {shown(entry.path)}</div><div>source: {shown(entry.provenance?.source)}</div><div>license: {shown(entry.provenance?.license_status)}</div><div>point-in-time: {shown(entry.provenance?.point_in_time_policy)}</div><div>adjustment: {shown(entry.provenance?.adjustment_policy)}</div><div>classification: {entry.provenance?.transformation_version ? 'transformed' : 'source snapshot'}</div></dl></details>)}</div></section>
                {!quality ? <div role="status" className="border-l-2 border-amber-400/50 pl-3 text-[11px] leading-relaxed text-slate-400">Load observed market data or execute a strategy to inspect its manifest. No quality values are inferred before then.</div> : <>
                    <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Manifest</h3><dl className="space-y-2 text-[10px]">
                        {[['Status', quality.status], ['Dataset ID', data.metadata?.provenance?.dataset_id || quality.source], ['Source', quality.source], ['As of', quality.as_of], ['Observations', quality.observations], ['Currency', quality.currency], ['Timezone', quality.timezone], ['Calendar', quality.calendar], ['Corporate actions', quality.corporate_actions], ['Look-ahead check', quality.look_ahead_check]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 border-b border-white/5 pb-2"><dt className="text-slate-500">{label}</dt><dd className="max-w-[220px] text-right text-slate-200">{shown(value)}</dd></div>)}
                    </dl></section>
                    <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Loaded coverage</h3><dl className="space-y-2 text-[10px]">
                        {[['First bar', summary.first], ['Last bar', summary.last], ['Loaded rows', data.candles.length], ['Missing loaded values', summary.missing]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 border-b border-white/5 pb-2"><dt className="text-slate-500">{label}</dt><dd className="text-right text-slate-200">{shown(value)}</dd></div>)}
                    </dl></section>
                    <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Observed schema</h3><div className="space-y-1 text-[10px] text-slate-300">{summary.fields.map((field) => <div key={field}>{field}</div>)}</div></section>
                    {data.metadata?.warnings?.length ? <section><h3 className="mb-2 text-[9px] font-bold uppercase tracking-widest text-amber-400">Warnings</h3><div className="space-y-2 text-[10px] text-amber-200">{data.metadata.warnings.map((warning, index) => <div key={warning.code || index}>{warning.message || warning.code || 'Unspecified warning'}</div>)}</div></section> : null}
                </>}
            </div>
        </aside>
    );
}
