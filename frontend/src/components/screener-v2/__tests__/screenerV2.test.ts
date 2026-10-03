import { runScreenerV2Feature } from '../api';
jest.mock('@/lib/api', () => ({ API_BASE_URL: 'http://localhost/api' }));

beforeEach(() => { global.fetch = jest.fn(); });

test('runs the owned job contract and publishes only completed real results', async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'j', status: 'queued' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'completed', result: { feature_id: '01', status: 'ok' } }) });
  await expect(runScreenerV2Feature('feature-01', { universe: 'master' })).resolves.toEqual({ feature_id: '01', status: 'ok' });
  expect(fetch).toHaveBeenNthCalledWith(1, 'http://localhost/api/screener-v2/feature/01/jobs', expect.objectContaining({ body: JSON.stringify({ payload: { universe: 'master' } }) }));
});

test('server errors propagate without demo fallback', async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: false, json: async () => ({ detail: 'Unknown tickers' }) });
  await expect(runScreenerV2Feature('01', {})).rejects.toThrow('Unknown tickers');
});
