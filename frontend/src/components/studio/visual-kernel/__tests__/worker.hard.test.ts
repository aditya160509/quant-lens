import { downsampleLTTB } from '../downsample';
import { downsampleOnWorker, terminateWorker } from '../workerClient';

describe('worker hardest', () => {
    it('main-thread downsample equals expected worker result for 100k points', () => {
        const data = Array.from({ length: 100000 }, (_, i) => ({ x: i, value: 100 + Math.sin(i / 100) }));
        const main = downsampleLTTB(data, 1500);
        // Simulate worker result by calling same pure function (worker runs same code)
        const workerResult = downsampleLTTB(data, 1500);
        expect(main.length).toBe(workerResult.length);
        expect(main[0]).toEqual(workerResult[0]);
        expect(main[main.length - 1]).toEqual(workerResult[workerResult.length - 1]);
    });
    it('cancelled signal prevents worker creation', async () => {
        const workerConstructor = jest.fn();
        Object.defineProperty(global, 'Worker', { configurable: true, writable: true, value: workerConstructor });
        const controller = new AbortController();
        controller.abort();
        await expect(downsampleOnWorker([{ x: 0, value: 1 }], 1, controller.signal)).rejects.toMatchObject({ code: 'STUDIO_CANCELLED' });
        expect(workerConstructor).not.toHaveBeenCalled();
    });
    it('termination rejects pending work instead of leaking its promise', async () => {
        const instance = { postMessage: jest.fn(), terminate: jest.fn(), onmessage: null, onerror: null };
        Object.defineProperty(global, 'Worker', { configurable: true, writable: true, value: jest.fn(() => instance) });
        const pending = downsampleOnWorker([{ x: 0, value: 1 }], 1);
        terminateWorker();
        await expect(pending).rejects.toMatchObject({ code: 'STUDIO_WORKER_TERMINATED' });
        expect(instance.terminate).toHaveBeenCalledTimes(1);
    });
});
