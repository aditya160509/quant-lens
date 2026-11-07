import { createStudioJob, getStudioJob, recordPromotionAudit, StudioApiError, studioRequest, waitForStudioJob, waitForStudioJobEvents } from '../studioApi';

describe('studioRequest', () => {
    beforeEach(() => {
        global.fetch = vi.fn();
    });

    afterEach(() => vi.restoreAllMocks());

    it('adds the contract version and request ID', async () => {
        const fetchMock = vi.mocked(global.fetch).mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: 'success' }),
        } as Response);

        await studioRequest('/execute', { method: 'POST', body: { code: 'pass' } });

        expect(fetchMock).toHaveBeenCalledWith('/api/studio/execute', expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({ 'X-Request-ID': expect.any(String) }),
            body: JSON.stringify({ contract_version: '1.0', code: 'pass' }),
        }));
    });

    it('normalizes the backend error envelope', async () => {
        vi.mocked(global.fetch).mockResolvedValue({
            ok: false,
            status: 422,
            json: async () => ({
                detail: { code: 'STRATEGY_INVALID', message: 'Script is invalid.', retryable: false },
            }),
        } as Response);

        await expect(studioRequest('/execute', { method: 'POST', body: {} })).rejects.toMatchObject({
            name: 'StudioApiError',
            code: 'STRATEGY_INVALID',
            status: 422,
            retryable: false,
        });
    });

    it('exports a typed error class', () => {
        expect(new StudioApiError('failure')).toBeInstanceOf(Error);
    });

    it('retries retryable GET responses once with the same request identity', async () => {
        const fetchMock = vi.mocked(global.fetch)
            .mockResolvedValueOnce({
                ok: false,
                status: 503,
                json: async () => ({ detail: { message: 'Unavailable', retryable: true } }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: async () => ({ status: 'success' }),
            } as Response);

        await expect(studioRequest('/data?ticker=SPY')).resolves.toEqual({ status: 'success' });
        expect(fetchMock).toHaveBeenCalledTimes(2);
        const firstHeaders = (fetchMock.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
        const secondHeaders = (fetchMock.mock.calls[1][1] as RequestInit).headers as Record<string, string>;
        expect(secondHeaders['X-Request-ID']).toBe(firstHeaders['X-Request-ID']);
    });

    it('rejects responses that fail an explicit contract validator', async () => {
        vi.mocked(global.fetch).mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ unexpected: true }),
        } as Response);

        await expect(studioRequest('/data', {
            validate: payload => payload?.status === 'success',
        })).rejects.toMatchObject({ code: 'STUDIO_CONTRACT_INVALID' });
    });

    it('reports caller cancellation without retrying', async () => {
        const controller = new AbortController();
        const fetchMock = vi.mocked(global.fetch).mockImplementation(async (_input, init) => {
            controller.abort();
            throw (init?.signal as AbortSignal).reason;
        });

        await expect(studioRequest('/data?ticker=SPY', {
            signal: controller.signal,
        })).rejects.toMatchObject({ code: 'STUDIO_CANCELLED', retryable: false });
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('creates and waits for a durable Studio job', async () => {
        const fetchMock = vi.mocked(global.fetch)
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: async () => ({ status: 'success', job: { job_id: 'job-1', status: 'queued' } }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: async () => ({ status: 'success', job: { job_id: 'job-1', status: 'completed', result: { candles: [] } } }),
            } as Response);

        const job = await createStudioJob('execute', { code: 'pass' }, { idempotencyKey: 'stable-job-key' });
        await expect(waitForStudioJob(job.job_id, { pollIntervalMs: 0 })).resolves.toEqual({ candles: [] });
        expect(fetchMock.mock.calls[0][0]).toBe('/api/studio/jobs');
        expect(fetchMock.mock.calls[1][0]).toBe('/api/studio/jobs/job-1');
    });

    it('retrieves a persisted Studio job by encoded ID', async () => {
        const fetchMock = vi.mocked(global.fetch).mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: 'success', job: { job_id: 'run/1', status: 'completed', result: { candles: [] } } }),
        } as Response);

        await expect(getStudioJob('run/1')).resolves.toMatchObject({ job_id: 'run/1', status: 'completed' });
        expect(fetchMock.mock.calls[0][0]).toBe('/api/studio/jobs/run%2F1');
    });

    it('streams named job events and resolves the authoritative persisted result', async () => {
        class MockEventSource {
            static instance: MockEventSource;
            listeners = new Map<string, (event: MessageEvent) => void>();
            close = vi.fn();
            constructor(public url: string) { MockEventSource.instance = this; }
            addEventListener(name: string, listener: (event: MessageEvent) => void) { this.listeners.set(name, listener); }
            emit(name: string, payload: unknown) { this.listeners.get(name)?.({ type: name, data: JSON.stringify(payload) } as MessageEvent); }
        }
        Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: MockEventSource });
        vi.mocked(global.fetch).mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: 'success', job: { job_id: 'job-2', status: 'completed', result: { status: 'success', paths: [] } } }),
        } as Response);
        const updates: unknown[] = [];

        const result = waitForStudioJobEvents('job-2', { onUpdate: (update) => updates.push(update), watchdogMs: 60_000 });
        // P15: EventSource cannot send headers, so the stream correlates via
        // ?request_id= (backend echoes it as X-Request-ID).
        expect(MockEventSource.instance.url).toMatch(/^\/api\/studio\/jobs\/job-2\/events\?request_id=[\w-]+$/);
        MockEventSource.instance.emit('running', { job_id: 'job-2', status: 'running', progress: 50 });
        MockEventSource.instance.emit('completed', { job_id: 'job-2', status: 'completed', progress: 100 });

        await expect(result).resolves.toEqual({ status: 'success', paths: [] });
        expect(updates).toContainEqual(expect.objectContaining({ status: 'running', progress: 50 }));
        expect(MockEventSource.instance.close).toHaveBeenCalled();
    });

    it('records a promotion decision against an encoded durable job ID', async () => {
        const fetchMock = vi.mocked(global.fetch).mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'success', audit: { audit_id: 'audit-1' } }) } as Response);

        await recordPromotionAudit('job/3', { action: 'override', actor: 'risk', rationale: 'Approved exception' });

        expect(fetchMock).toHaveBeenCalledWith('/api/studio/jobs/job%2F3/promotion-audit', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ contract_version: '1.0', action: 'override', actor: 'risk', rationale: 'Approved exception' }),
        }));
    });
});
