const CONTRACT_VERSION = '1.0';
const DEFAULT_TIMEOUT_MS = 30_000;
const RETRYABLE_STATUS = new Set([408, 425, 429, 502, 503, 504]);

export class StudioApiError extends Error {
    constructor(message, { code = 'STUDIO_REQUEST_FAILED', status = 0, retryable = false, requestId = null } = {}) {
        super(message);
        this.name = 'StudioApiError';
        this.code = code;
        this.status = status;
        this.retryable = retryable;
        this.requestId = requestId;
    }
}

const requestId = () => globalThis.crypto?.randomUUID?.() ?? `studio-${Date.now()}`;
const wait = (milliseconds) => new Promise(resolve => setTimeout(resolve, milliseconds));
const waitWithSignal = (milliseconds, signal) => new Promise((resolve, reject) => {
    const onAbort = () => {
        clearTimeout(timer);
        reject(new StudioApiError('Studio request was cancelled.', { code: 'STUDIO_CANCELLED' }));
    };
    const timer = setTimeout(() => {
        signal?.removeEventListener('abort', onAbort);
        resolve();
    }, milliseconds);
    if (signal?.aborted) onAbort();
    else signal?.addEventListener('abort', onAbort, { once: true });
});

export async function createStudioJob(type, params, { signal, idempotencyKey } = {}) {
    const payload = await studioRequest('/jobs', {
        method: 'POST',
        signal,
        body: {
            type,
            params,
            idempotency_key: idempotencyKey || requestId(),
        },
    });
    if (!payload?.job?.job_id) {
        throw new StudioApiError('Studio did not return a job identifier.', { code: 'STUDIO_JOB_INVALID' });
    }
    return payload.job;
}

export async function waitForStudioJob(jobId, { signal, pollIntervalMs = 250 } = {}) {
    for (;;) {
        const payload = await studioRequest(`/jobs/${encodeURIComponent(jobId)}`, { signal, retries: 1 });
        const job = payload?.job;
        if (!job) throw new StudioApiError('Studio job disappeared.', { code: 'STUDIO_JOB_INVALID' });
        if (job.status === 'completed') return job.result;
        if (job.status === 'failed' || job.status === 'partial') {
            throw new StudioApiError(job.error || `Studio job ended with status ${job.status}.`, { code: 'STUDIO_JOB_FAILED' });
        }
        if (job.status === 'cancelled') {
            throw new StudioApiError('Studio job was cancelled.', { code: 'STUDIO_CANCELLED' });
        }
        await waitWithSignal(pollIntervalMs, signal);
    }
}

export function waitForStudioJobEvents(jobId, { signal = undefined, onUpdate = undefined, watchdogMs = 5_000 } = {}) {
    if (typeof EventSource === 'undefined') return waitForStudioJob(jobId, { signal });
    return new Promise((resolve, reject) => {
        // P15: EventSource cannot send headers, so the stream correlates via
        // ?request_id=; the backend echoes it as X-Request-ID and joins it
        // with the middleware request ID in structured logs.
        const streamRequestId = requestId();
        const source = new EventSource(`/api/studio/jobs/${encodeURIComponent(jobId)}/events?request_id=${encodeURIComponent(streamRequestId)}`);
        let settled = false;
        let watchdog = null;
        const finish = async (status) => {
            if (settled) return;
            settled = true;
            source.close();
            if (watchdog) clearInterval(watchdog);
            signal?.removeEventListener('abort', abort);
            try {
                const job = await getStudioJob(jobId, { signal });
                onUpdate?.(job);
                if (status === 'completed' && job.status === 'completed') resolve(job.result);
                else if (job.status === 'cancelled') reject(new StudioApiError('Studio job was cancelled.', { code: 'STUDIO_CANCELLED' }));
                else reject(new StudioApiError(job.error || `Studio job ended with status ${job.status}.`, { code: 'STUDIO_JOB_FAILED' }));
            } catch (error) { reject(error); }
        };
        const receive = (event) => {
            let update;
            try { update = JSON.parse(event.data); } catch { return; }
            onUpdate?.(update);
            if (['completed', 'failed', 'partial', 'cancelled'].includes(event.type)) finish(event.type);
        };
        ['queued', 'running', 'cancelling', 'completed', 'failed', 'partial', 'cancelled'].forEach((status) => source.addEventListener(status, receive));
        const abort = () => {
            if (settled) return;
            settled = true;
            source.close();
            if (watchdog) clearInterval(watchdog);
            reject(new StudioApiError('Studio request was cancelled.', { code: 'STUDIO_CANCELLED' }));
        };
        if (signal?.aborted) abort();
        else signal?.addEventListener('abort', abort, { once: true });
        // EventSource reconnects with Last-Event-ID automatically. This sparse read
        // watchdog also resolves jobs when a proxy suppresses event-stream delivery.
        watchdog = setInterval(async () => {
            if (settled) return;
            try {
                const job = await getStudioJob(jobId, { signal });
                onUpdate?.(job);
                if (['completed', 'failed', 'partial', 'cancelled'].includes(job.status)) finish(job.status);
            } catch (error) {
                if (signal?.aborted) abort();
            }
        }, watchdogMs);
    });
}

export async function runSensitivityGrid({ closes, lookbacks, thresholds, slippageBps = 0, commissionPct = 0 }, { signal } = {}) {
    return studioRequest('/validation/sensitivity', {
        method: 'POST',
        signal,
        body: { closes, lookbacks, thresholds, slippage_bps: slippageBps, commission_pct: commissionPct },
    });
}

export async function runValidationScenarios({ returns, oosDays = 20, nFolds = 5, purgeDays = 0, embargoDays = 0, costShockBps = 10, missingPct = 5, delayBars = 1 }, { signal } = {}) {
    return studioRequest('/validation/scenarios', {
        method: 'POST',
        signal,
        body: { returns, oos_days: oosDays, n_folds: nFolds, purge_days: purgeDays, embargo_days: embargoDays, cost_shock_bps: costShockBps, missing_pct: missingPct, delay_bars: delayBars },
    });
}

export async function getStudioJob(jobId, { signal } = {}) {
    if (!jobId) throw new StudioApiError('Studio job ID is required.', { code: 'STUDIO_JOB_ID_REQUIRED' });
    const payload = await studioRequest(`/jobs/${encodeURIComponent(jobId)}`, { signal, retries: 1 });
    if (!payload?.job?.job_id) {
        throw new StudioApiError('Studio did not return a valid job record.', { code: 'STUDIO_JOB_INVALID' });
    }
    return payload.job;
}

export async function cancelStudioJob(jobId) {
    return studioRequest(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
}

export async function recordPromotionAudit(jobId, decision, { signal } = {}) {
    return studioRequest(`/jobs/${encodeURIComponent(jobId)}/promotion-audit`, { method: 'POST', body: decision, signal });
}

export async function getPromotionAudit(jobId, { signal } = {}) {
    return studioRequest(`/jobs/${encodeURIComponent(jobId)}/promotion-audit`, { signal });
}

export async function studioRequest(path, {
    method = 'GET',
    body = undefined,
    signal = undefined,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    retries = method.toUpperCase() === 'GET' ? 1 : 0,
    validate = undefined,
} = {}) {
    const id = requestId();
    const normalizedMethod = method.toUpperCase();
    let lastError;

    for (let attempt = 0; attempt <= Math.max(0, retries); attempt += 1) {
        const timeoutController = new AbortController();
        const timer = setTimeout(() => timeoutController.abort(), timeoutMs);
        const combinedSignal = signal
            ? AbortSignal.any([signal, timeoutController.signal])
            : timeoutController.signal;
        try {
            const response = await fetch(`/api/studio${path}`, {
                method: normalizedMethod,
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-Request-ID': id,
                },
                body: body === undefined ? undefined : JSON.stringify({ contract_version: CONTRACT_VERSION, ...body }),
                signal: combinedSignal,
            });
            const payload = await response.json().catch(() => null);
            if (!response.ok || payload?.status === 'error') {
                const detail = payload?.detail?.message ? payload.detail : payload;
                const error = new StudioApiError(detail?.message || `Studio request failed with HTTP ${response.status}.`, {
                    code: detail?.code,
                    status: response.status,
                    retryable: detail?.retryable ?? RETRYABLE_STATUS.has(response.status),
                    requestId: detail?.request_id || id,
                });
                if (normalizedMethod === 'GET' && error.retryable && attempt < retries) {
                    lastError = error;
                    await wait(200 * (attempt + 1));
                    continue;
                }
                throw error;
            }
            if (validate && !validate(payload)) {
                throw new StudioApiError('Studio response did not match the expected contract.', {
                    code: 'STUDIO_CONTRACT_INVALID',
                    status: response.status,
                    requestId: id,
                });
            }
            return payload;
        } catch (error) {
            if (error instanceof StudioApiError) throw error;
            if (signal?.aborted) {
                throw new StudioApiError('Studio request was cancelled.', {
                    code: 'STUDIO_CANCELLED',
                    retryable: false,
                    requestId: id,
                });
            }
            const timedOut = timeoutController.signal.aborted && !signal?.aborted;
            lastError = new StudioApiError(timedOut ? 'Studio request timed out.' : 'Studio request could not be completed.', {
                code: timedOut ? 'STUDIO_TIMEOUT' : 'STUDIO_NETWORK_ERROR',
                retryable: true,
                requestId: id,
            });
            if (normalizedMethod === 'GET' && !timedOut && !signal?.aborted && attempt < retries) {
                await wait(200 * (attempt + 1));
                continue;
            }
            throw lastError;
        } finally {
            clearTimeout(timer);
        }
    }
    throw lastError;
}
