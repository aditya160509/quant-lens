"use client";
import { useCallback, useRef } from "react";
import { cancelStudioJob, createStudioJob, waitForStudioJobEvents } from "@/lib/studioApi";
import { useStudioResultStore } from "@/stores/studio/resultStore";
import { isStudioMonteCarloResponse, isStudioWalkForwardResponse } from "@/lib/studioValidators";

export function useStudioAnalysis() {
    const setData = useStudioResultStore((s) => s.setData);
    const setMcLoading = useStudioResultStore((s) => s.setMcLoading);
    const setMcError = useStudioResultStore((s) => s.setMcError);
    const setMcJob = useStudioResultStore((s) => s.setMcJob);
    const setWfLoading = useStudioResultStore((s) => s.setWfLoading);
    const setWfError = useStudioResultStore((s) => s.setWfError);
    const setWfJob = useStudioResultStore((s) => s.setWfJob);
    const equityCurve = useStudioResultStore((s) => s.data.equityCurve);
    const monteCarloRunRef = useRef(null);
    const walkForwardRunRef = useRef(null);

    const cancelRun = useCallback((runRef, setLoading, setError, label) => {
        const active = runRef.current;
        active?.controller.abort();
        if (active?.jobId) cancelStudioJob(active.jobId).catch(() => {});
        runRef.current = null;
        setLoading(false);
        setError(`${label} cancelled.`);
    }, []);

    const cancelMonteCarlo = useCallback(() => {
        cancelRun(monteCarloRunRef, setMcLoading, setMcError, 'Monte Carlo simulation');
    }, [cancelRun, setMcError, setMcLoading]);

    const cancelWalkForward = useCallback(() => {
        cancelRun(walkForwardRunRef, setWfLoading, setWfError, 'Walk-forward validation');
    }, [cancelRun, setWfError, setWfLoading]);

    const runMonteCarlo = useCallback(async (simulations = 10000, method = 'gaussian', blockSize = 5, returnsOverride = null, sourceArtifactId = null) => {
        if ((!returnsOverride || returnsOverride.length < 20) && (!equityCurve || equityCurve.length < 20)) {
            setMcError('Execute a strategy with at least 20 equity observations before simulation.');
            return;
        }
        cancelMonteCarlo();
        const controller = new AbortController();
        const active = { controller, jobId: null };
        monteCarloRunRef.current = active;
        setMcLoading(true);
        setMcError(null);
        setMcJob(null);
        const rets = returnsOverride || equityCurve.slice(1).map((v, i) => (v - equityCurve[i]) / equityCurve[i]);
        try {
            const job = await createStudioJob('monte-carlo', { returns: rets, simulations, time_horizon: 252, method, block_size: blockSize, seed: 42, source_artifact_id: sourceArtifactId }, { signal: controller.signal });
            active.jobId = job.job_id;
            setMcJob(job);
            const resData = await waitForStudioJobEvents(job.job_id, { signal: controller.signal, onUpdate: (update) => setMcJob((current) => ({ ...current, ...update })) });
            if (!isStudioMonteCarloResponse(resData)) throw new Error('Monte Carlo result did not match the expected contract.');
            if (resData.status === 'success') setData((prev) => ({ ...prev, mcData: resData }));
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') return;
            setData((prev) => ({ ...prev, mcData: null }));
            setMcError(e instanceof Error ? e.message : 'Monte Carlo simulation failed.');
        } finally {
            if (monteCarloRunRef.current === active) {
                monteCarloRunRef.current = null;
                setMcLoading(false);
            }
        }
    }, [cancelMonteCarlo, equityCurve, setData, setMcError, setMcJob, setMcLoading]);

    const runWalkForward = useCallback(async (nFolds = 5, purgeDays = 0, embargoDays = 0, minOosSharpe = 0.5, minConsistencyPct = 50, returnsOverride = null, sourceArtifactId = null) => {
        if ((!returnsOverride || returnsOverride.length < 100) && (!equityCurve || equityCurve.length < 100)) {
            setWfError('Execute a strategy with at least 100 equity observations before validation.');
            return;
        }
        cancelWalkForward();
        const controller = new AbortController();
        const active = { controller, jobId: null };
        walkForwardRunRef.current = active;
        setWfLoading(true);
        setWfError(null);
        setWfJob(null);
        const returns = returnsOverride || equityCurve.slice(1).map((value, index) => (value - equityCurve[index]) / equityCurve[index]);
        try {
            const job = await createStudioJob('walk-forward', { returns, n_folds: nFolds, oos_days: 20, purge_days: purgeDays, embargo_days: embargoDays, min_oos_sharpe: minOosSharpe, min_consistency_pct: minConsistencyPct, source_artifact_id: sourceArtifactId }, { signal: controller.signal });
            active.jobId = job.job_id;
            setWfJob(job);
            const resData = await waitForStudioJobEvents(job.job_id, { signal: controller.signal, onUpdate: (update) => setWfJob((current) => ({ ...current, ...update })) });
            if (!isStudioWalkForwardResponse(resData)) throw new Error('Walk-forward result did not match the expected contract.');
            setData((prev) => ({ ...prev, wfData: resData }));
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') return;
            setData((prev) => ({ ...prev, wfData: null }));
            setWfError(e instanceof Error ? e.message : 'Walk-forward validation failed.');
        } finally {
            if (walkForwardRunRef.current === active) {
                walkForwardRunRef.current = null;
                setWfLoading(false);
            }
        }
    }, [cancelWalkForward, equityCurve, setData, setWfError, setWfJob, setWfLoading]);

    return { runMonteCarlo, runWalkForward, cancelMonteCarlo, cancelWalkForward };
}
