/**
 * Worker client — single worker, id-based, AbortSignal aware.
 */

let worker = null;
let nextId = 1;
const pending = new Map();

function getWorker() {
    if (worker) return worker;
    // Use module worker where supported; fallback to classic
    try {
        worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
    } catch {
        worker = new Worker(new URL('./worker.js', import.meta.url));
    }
    worker.onmessage = (e) => {
        const { id, status, result, error } = e.data;
        const entry = pending.get(id);
        if (!entry) return;
        pending.delete(id);
        entry.cleanup();
        if (status === 'completed') entry.resolve(result);
        else if (status === 'cancelled') entry.reject(Object.assign(new Error('cancelled'), { code: 'STUDIO_CANCELLED' }));
        else entry.reject(new Error(error || 'worker failed'));
    };
    worker.onerror = (e) => {
        pending.forEach(({ reject, cleanup }) => {
            cleanup();
            reject(new Error(e.message || 'worker error'));
        });
        pending.clear();
    };
    return worker;
}

export function downsampleOnWorker(data, threshold, signal) {
    return new Promise((resolve, reject) => {
        const id = String(nextId++);
        if (signal?.aborted) {
            reject(Object.assign(new Error('cancelled'), { code: 'STUDIO_CANCELLED' }));
            return;
        }
        let activeWorker;
        const onAbort = () => {
            activeWorker?.postMessage({ id, signalAborted: true });
            pending.delete(id);
            reject(Object.assign(new Error('cancelled'), { code: 'STUDIO_CANCELLED' }));
        };
        const cleanup = () => signal?.removeEventListener('abort', onAbort);
        pending.set(id, { resolve, reject, cleanup });
        signal?.addEventListener('abort', onAbort, { once: true });
        activeWorker = getWorker();
        activeWorker.postMessage({ id, op: 'downsample', payload: { data, threshold } });
    });
}

export function terminateWorker() {
    worker?.terminate();
    worker = null;
    pending.forEach(({ reject, cleanup }) => {
        cleanup();
        reject(Object.assign(new Error('worker terminated'), { code: 'STUDIO_WORKER_TERMINATED' }));
    });
    pending.clear();
}
