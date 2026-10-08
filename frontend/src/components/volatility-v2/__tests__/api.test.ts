import { runVolatilityV2Feature, toVolatilityPayload } from '../api';

const contract = { id: '01', inputs: [{key:'assets'}, {key:'asset'}, {key:'rolling_window'}], aliases: {window_days:'rolling_window'} };

test('payload follows backend aliases and rejects unsupported calculations', () => {
 expect(toVolatilityPayload({assets:'SPY', rolling_window:'21', window_days:'21', compute_mode:'realtime'},contract)).toEqual({assets:'SPY',rolling_window:'21'});
 expect(() => toVolatilityPayload({made_up:'x'},contract)).toThrow('Unsupported control');
 expect(() => toVolatilityPayload({rolling_window:'21',window_days:'42'},contract)).toThrow('Conflicting');
});

test('run obtains the manifest and returns the actual completed background result', async () => {
 const result = {feature_id:'feature_01', charts:{five_estimator_comparison:[{cc:.2}]}};
 global.fetch = jest.fn()
   .mockResolvedValueOnce({ok:true,json:async()=>({features:[contract]})})
   .mockResolvedValueOnce({ok:true,json:async()=>({job_id:'observed-job'})})
   .mockResolvedValueOnce({ok:true,json:async()=>({status:'completed',result})});
 expect(await runVolatilityV2Feature('01',{assets:'SPY'})).toEqual(result);
 expect(fetch.mock.calls[1][0]).toContain('/feature/01/jobs');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({payload:{assets:'SPY'}});
});

test('backend errors remain errors, with no demo fallback', async () => {
 global.fetch = jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Unknown symbols'})});
 await expect(runVolatilityV2Feature('01',{assets:'FAKE'})).rejects.toThrow('Unknown symbols');
});
