import { runFactorsV2Feature, runFactorsV2All } from '@/lib/api';

beforeEach(() => { global.fetch = jest.fn(); });

test('wraps inputs and waits for the real job result', async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ok:true,json:async()=>({job_id:'j'})})
    .mockResolvedValueOnce({ok:true,json:async()=>({status:'completed',result:{feature_id:'feature_08'}})});
  await expect(runFactorsV2Feature('feature-08',{half_life:17})).resolves.toEqual({feature_id:'feature_08'});
  expect(fetch).toHaveBeenNthCalledWith(1,expect.stringContaining('/labs/factors/v2/feature/08/jobs'),expect.objectContaining({body:JSON.stringify({payload:{half_life:17}})}));
});

test('propagates job failure without fabricated fallback', async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ok:true,json:async()=>({job_id:'j'})})
    .mockResolvedValueOnce({ok:true,json:async()=>({status:'failed',error:'Missing held quote'})});
  await expect(runFactorsV2Feature('07',{})).rejects.toThrow('Missing held quote');
});

test('merges explicit batch payloads before queuing', async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ok:true,json:async()=>({job_id:'j'})})
    .mockResolvedValueOnce({ok:true,json:async()=>({status:'completed',result:{status:'ok'}})});
  await runFactorsV2All({as_of_date:'2023-01-01'},{'08':{half_life:17}});
  expect(fetch).toHaveBeenNthCalledWith(1,expect.stringContaining('/run-all'),expect.objectContaining({body:JSON.stringify({feature_payloads:{'08':{as_of_date:'2023-01-01',half_life:17}}})}));
});
