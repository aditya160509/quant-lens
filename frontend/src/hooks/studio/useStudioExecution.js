"use client";
import { useCallback, useRef } from "react";
import { cancelStudioJob, createStudioJob, studioRequest, waitForStudioJob } from "@/lib/studioApi";
import { useStudioResultStore } from "@/stores/studio/resultStore";
import { useStudioWorkspaceStore } from "@/stores/studio/workspaceStore";
import { useStudioEditorStore } from "@/stores/studio/editorStore";
import { useStudioLayoutStore } from "@/stores/studio/layoutStore";
import { useStudioPreferenceStore } from "@/stores/studio/preferenceStore";
import { isStudioExecutionResponse, isStudioDataResponse } from "@/lib/studioValidators";

// P5-W2 polish: client-side quota/limit display mirrored from backend
// conventions (backend/app/services/studio/conventions.py + execution.py).
// These are display guards only — the backend remains authoritative.
export const STUDIO_QUOTAS = Object.freeze({
    maxCodeBytes: 64 * 1024,
    maxSignals: 100_000,
    maxResponseBytes: 4 * 1024 * 1024,
    maxSlippageBps: 50.0,
    maxCommissionPct: 1.0,
    maxLookbackYears: 30,
    executionMode: 'isolated_one_shot',
});

// Rough client-side compute estimate for quota display: bytes + signal
// budget share. Never sent to the server; shown next to picker/quota UI.
export function estimateComputeQuota(code) {
    const bytes = new Blob([code || '']).size;
    return {
        codeBytes: bytes,
        codeBytesPct: Math.min(100, Math.round((bytes / STUDIO_QUOTAS.maxCodeBytes) * 100)),
        withinQuota: bytes <= STUDIO_QUOTAS.maxCodeBytes,
    };
}

export function useStudioExecution() {
    const data = useStudioResultStore((s) => s.data);
    const setData = useStudioResultStore((s) => s.setData);
    const setDataA = useStudioResultStore((s) => s.setDataA);
    const setDataB = useStudioResultStore((s) => s.setDataB);
    const setGridData = useStudioResultStore((s) => s.setGridData);
    const setGridDataA = useStudioResultStore((s) => s.setGridDataA);
    const setGridDataB = useStudioResultStore((s) => s.setGridDataB);
    const setGridVsView = useStudioResultStore((s) => s.setGridVsView);
    const setIsExecuting = useStudioResultStore((s) => s.setIsExecuting);
    const setExecutionError = useStudioResultStore((s) => s.setExecutionError);
    const setIsPlaying = useStudioResultStore((s) => s.setIsPlaying);
    const setPlayIndex = useStudioResultStore((s) => s.setPlayIndex);
    const setAnalysisComplete = useStudioResultStore((s) => s.setAnalysisComplete);
    const setPreviousEquityCurve = useStudioResultStore((s) => s.setPreviousEquityCurve);
    const setPreviousSignals = useStudioResultStore((s) => s.setPreviousSignals);
    const setDataLoading = useStudioResultStore((s) => s.setDataLoading);
    const setDataError = useStudioResultStore((s) => s.setDataError);
    const setGridLoading = useStudioResultStore((s) => s.setGridLoading);
    const setGridError = useStudioResultStore((s) => s.setGridError);

    const ticker = useStudioWorkspaceStore((s) => s.ticker);
    const slippageBps = useStudioWorkspaceStore((s) => s.slippageBps);
    const commissionPct = useStudioWorkspaceStore((s) => s.commissionPct);
    const codeA = useStudioEditorStore((s) => s.codeA);
    const codeB = useStudioEditorStore((s) => s.codeB);
    const vsModeActive = useStudioEditorStore((s) => s.vsModeActive);
    const playSpeed = useStudioPreferenceStore((s) => s.playSpeed);
    const gridConfig = useStudioLayoutStore((s) => s.gridConfig);
    const setKernelCollapsed = useStudioPreferenceStore((s) => s.setKernelCollapsed);
    const setShowIndicatorSelect = useStudioWorkspaceStore((s) => s.setShowIndicatorSelect);

    const executionControllerRef = useRef(null);
    const activeJobIdsRef = useRef(new Set());
    const playIntervalRef = useRef(null);

    const calculateVolumeProfile = useCallback((candles) => {
        if (!candles || candles.length === 0) return [];
        const prices = candles.map((c) => c.close);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        const priceRange = maxPrice - minPrice;
        const numBuckets = 30;
        if (priceRange <= 0) {
            const volume = candles.reduce((t, c) => t + c.volume, 0);
            return [{ priceLevel: minPrice, volume, normalized: volume > 0 ? 1 : 0 }];
        }
        const bucketSize = priceRange / numBuckets;
        const profile = Array(numBuckets).fill(0).map((_, i) => ({ priceLevel: minPrice + bucketSize * i + bucketSize / 2, volume: 0 }));
        candles.forEach((c) => {
            const bucketIdx = Math.min(Math.floor((c.close - minPrice) / bucketSize), numBuckets - 1);
            if (bucketIdx >= 0 && bucketIdx < numBuckets) profile[bucketIdx].volume += c.volume;
        });
        const maxVol = Math.max(...profile.map((p) => p.volume));
        return profile.map((p) => ({ ...p, normalized: maxVol > 0 ? p.volume / maxVol : 0 }));
    }, []);

    const startPlayback = useCallback((totalCandles, speed = 20) => {
        if (playIntervalRef.current) clearInterval(playIntervalRef.current);
        setPlayIndex(0);
        setIsPlaying(true);
        setAnalysisComplete(false);
        let idx = 0;
        const intervalMs = speed;
        const interval = setInterval(() => {
            idx += 1;
            if (idx >= totalCandles - 1) {
                idx = totalCandles - 1;
                setPlayIndex(idx);
                setIsPlaying(false);
                setAnalysisComplete(true);
                clearInterval(interval);
            } else setPlayIndex(idx);
        }, intervalMs);
        playIntervalRef.current = interval;
    }, [setAnalysisComplete, setIsPlaying, setPlayIndex]);

    const executeStrategy = useCallback(async () => {
        const primaryCode = codeA;
        if (!primaryCode) return;
        executionControllerRef.current?.abort();
        const controller = new AbortController();
        executionControllerRef.current = controller;
        setKernelCollapsed(true);
        setShowIndicatorSelect(false);
        setIsExecuting(true);
        setExecutionError(null);
        setIsPlaying(false);
        setPlayIndex(0);
        setAnalysisComplete(false);
        if (data.equityCurve?.length > 0) setPreviousEquityCurve([...data.equityCurve]);
        if (data.signals?.length > 0) setPreviousSignals([...data.signals]);
        if (playIntervalRef.current) clearInterval(playIntervalRef.current);
        try {
            const runExecRequest = async (c, t) => {
                const params = { code: c, ticker: t, slippage_bps: slippageBps, commission_pct: commissionPct, universe: 'US_TOP50', lookback_years: 10, end_date: new Date().toISOString().split('T')[0] };
                const job = await createStudioJob('execute', params, { signal: controller.signal });
                activeJobIdsRef.current.add(job.job_id);
                try {
                    const result = await waitForStudioJob(job.job_id, { signal: controller.signal });
                    if (!isStudioExecutionResponse(result)) throw new Error('Studio execution result did not match the expected contract.');
                    return { ...result, job_id: job.job_id };
                } finally {
                    activeJobIdsRef.current.delete(job.job_id);
                }
            };
            const processData = (res) => ({ candles: res.candles || [], signals: res.signals || [], metrics: res.metrics || {}, trades: res.trades || [], equityCurve: res.equity_curve || [], series: res.series || null, metadata: res.metadata || null, runId: res.job_id || null, volumeProfile: calculateVolumeProfile(res.candles || []) });
            if (gridConfig.layoutId === '1x1') {
                const resA = await runExecRequest(codeA, ticker || 'SPY');
                let resB = null;
                if (vsModeActive) resB = await runExecRequest(codeB, ticker || 'SPY');
                if (resA.status === 'success') {
                    const formattedA = processData(resA);
                    setDataA(formattedA);
                    setData(formattedA);
                    if (resB && resB.status === 'success') setDataB(processData(resB));
                    if (formattedA.candles.length > 0) { startPlayback(formattedA.candles.length, playSpeed); return; }
                }
            } else {
                const resultsA = await Promise.all(gridConfig.tickers.map((t) => runExecRequest(codeA, t)));
                const formattedA = resultsA.map((res) => (res.status === 'success' ? processData(res) : null));
                let formattedB = [];
                if (vsModeActive) {
                    const resultsB = await Promise.all(gridConfig.tickers.map((t) => runExecRequest(codeB, t)));
                    formattedB = resultsB.map((res) => (res.status === 'success' ? processData(res) : null));
                    setGridDataB(formattedB);
                    setGridVsView('A');
                } else setGridDataB([]);
                setGridDataA(formattedA);
                setGridData(formattedA);
                const master = formattedA[0];
                if (master && master.candles.length > 0) { setData(master); startPlayback(master.candles.length, playSpeed); return; }
            }
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') { if (executionControllerRef.current === controller) setExecutionError('Stopped waiting for this run. The isolated runner may finish before its server timeout.'); }
            else setExecutionError(e instanceof Error ? e.message : 'Strategy execution failed.');
        } finally { if (executionControllerRef.current === controller) { executionControllerRef.current = null; setIsExecuting(false); } }
    }, [codeA, codeB, vsModeActive, ticker, slippageBps, commissionPct, playSpeed, startPlayback, data.equityCurve, data.signals, calculateVolumeProfile, gridConfig.layoutId, gridConfig.tickers, setAnalysisComplete, setData, setDataA, setDataB, setExecutionError, setGridData, setGridDataA, setGridDataB, setGridVsView, setIsExecuting, setIsPlaying, setKernelCollapsed, setPlayIndex, setPreviousEquityCurve, setPreviousSignals, setShowIndicatorSelect]);

    const cancelExecution = useCallback(() => {
        const pendingJobs = [...activeJobIdsRef.current];
        executionControllerRef.current?.abort();
        pendingJobs.forEach((jobId) => cancelStudioJob(jobId).catch(() => {}));
        setIsExecuting(false);
        setExecutionError('Execution cancelled. A runner already inside bounded strategy code may stop at its server timeout.');
    }, [setExecutionError, setIsExecuting]);

    const fetchData = useCallback(async (currentTicker, signal) => {
        if (!currentTicker) { setData({ candles: [], signals: [], metrics: {}, trades: [], equityCurve: [] }); setDataLoading(false); setDataError(null); return; }
        setDataLoading(true); setDataError(null);
        try {
            const resData = await studioRequest(`/data?ticker=${encodeURIComponent(currentTicker)}&lookback_years=10`, { signal, validate: isStudioDataResponse });
            if (resData.status === 'success') { setData((prev) => ({ ...prev, candles: resData.candles || [], signals: [], metrics: {}, trades: [], equityCurve: [], metadata: resData.metadata || null, volumeProfile: calculateVolumeProfile(resData.candles || []) })); setPlayIndex(0); setAnalysisComplete(false); }
        } catch (e) { if (e?.code === 'STUDIO_CANCELLED') return; setDataError(e instanceof Error ? e.message : 'Market data request failed.'); } finally { if (!signal?.aborted) setDataLoading(false); }
    }, [calculateVolumeProfile, setAnalysisComplete, setData, setDataError, setDataLoading, setPlayIndex]);

    const stopPlayback = useCallback(() => { if (playIntervalRef.current) clearInterval(playIntervalRef.current); setIsPlaying(false); }, [setIsPlaying]);

    // P5-W2 polish: run the current Monaco selection as its own job through
    // the same `execute` job type. `source: 'selection'` is a client-side
    // label — the backend validates the snippet with the same bounded policy
    // (class Strategy required), so a bare expression is truthfully rejected
    // with the policy error rather than silently wrapped.
    const executeSelection = useCallback(async (selectedCode) => {
        const snippet = (selectedCode || '').trim();
        if (!snippet) {
            setExecutionError('No selection to run — highlight code in the editor first.');
            return;
        }
        const quota = estimateComputeQuota(snippet);
        if (!quota.withinQuota) {
            setExecutionError(`Selection exceeds the ${STUDIO_QUOTAS.maxCodeBytes}-byte code budget.`);
            return;
        }
        executionControllerRef.current?.abort();
        const controller = new AbortController();
        executionControllerRef.current = controller;
        setIsExecuting(true);
        setExecutionError(null);
        setAnalysisComplete(false);
        try {
            const params = { code: snippet, ticker: ticker || 'SPY', slippage_bps: slippageBps, commission_pct: commissionPct, universe: 'US_TOP50', lookback_years: 10, end_date: new Date().toISOString().split('T')[0], source: 'selection' };
            const job = await createStudioJob('execute', params, { signal: controller.signal });
            activeJobIdsRef.current.add(job.job_id);
            try {
                const result = await waitForStudioJob(job.job_id, { signal: controller.signal });
                if (!isStudioExecutionResponse(result)) throw new Error('Studio execution result did not match the expected contract.');
                const formatted = { candles: result.candles || [], signals: result.signals || [], metrics: result.metrics || {}, trades: result.trades || [], equityCurve: result.equity_curve || [], series: result.series || null, metadata: result.metadata || null, runId: job.job_id || null, volumeProfile: calculateVolumeProfile(result.candles || []) };
                if (formatted.metadata && !formatted.metadata.selection) formatted.metadata = { ...formatted.metadata, selection: true };
                setData(formatted);
                if (formatted.candles.length > 0) startPlayback(formatted.candles.length, playSpeed);
            } finally {
                activeJobIdsRef.current.delete(job.job_id);
            }
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') setExecutionError('Stopped waiting for this run. The isolated runner may finish before its server timeout.');
            else setExecutionError(e instanceof Error ? e.message : 'Selection execution failed.');
        } finally { if (executionControllerRef.current === controller) { executionControllerRef.current = null; setIsExecuting(false); } }
    }, [ticker, slippageBps, commissionPct, playSpeed, startPlayback, calculateVolumeProfile, setAnalysisComplete, setData, setExecutionError, setIsExecuting]);

    return { executeStrategy, executeSelection, cancelExecution, fetchData, stopPlayback, calculateVolumeProfile };
}
