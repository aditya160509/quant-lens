import { buildReplayEvents, compareReplayRuns, matchesReplayBreakpoint, positionStateAtCursor, replayFillCausality } from '../studioReplay';

const run = {
    candles: [
        { time: 2, open: 101, high: 103, low: 100, close: 102, volume: 20 },
        { time: 1, open: 100, high: 102, low: 99, close: 101, volume: 10 },
    ],
    signals: [
        { date: '1970-01-01T00:00:01.000Z', timestamp: 1000, direction: 1, price: 101, idx: 1 },
        { date: '1970-01-01T00:00:02.000Z', timestamp: 2000, direction: -1, price: 102, idx: 2 },
    ],
    trades: [{ entry_date: '1970-01-01T00:00:01.000Z', exit_date: '1970-01-01T00:00:02.000Z', direction: 1, entry_price: 101, exit_price: 102, pnl: 0.01 }],
    equityCurve: [1, 1.01, 1.02],
};

describe('buildReplayEvents', () => {
    it('creates the same immutable ordered stream from the same artifact', () => {
        const first = buildReplayEvents(run);
        const second = buildReplayEvents(run);

        expect(first).toEqual(second);
        expect(first.map((event) => event.timestamp)).toEqual([...first.map((event) => event.timestamp)].sort((a, b) => a - b));
        expect(first.every(Object.isFrozen)).toBe(true);
        expect(Object.isFrozen(first)).toBe(true);
    });

    it('links the observed close and P&L transition to its open and exit signal', () => {
        const events = buildReplayEvents(run);
        const close = events.find((event) => event.type === 'position_close');

        expect(close?.payload.net_return).toBe(0.01);
        expect(close?.causal_event_ids).toEqual(['position_open:0', 'signal:1']);
        expect(events.some((event) => event.event_id === close?.causal_event_ids[0])).toBe(true);
        expect(events.some((event) => event.event_id === close?.causal_event_ids[1])).toBe(true);
    });

    it('does not mutate the source artifact or synthesize order and fill events', () => {
        const before = JSON.stringify(run);
        const events = buildReplayEvents(run);

        expect(JSON.stringify(run)).toBe(before);
        expect(events.some((event) => event.type === 'order' || event.type === 'fill')).toBe(false);
    });

    it('reports the first deterministic event divergence without rerunning either strategy', () => {
        const changed = { ...run, candles: run.candles.map((candle, index) => index === 0 ? { ...candle, close: 99 } : candle) };
        expect(compareReplayRuns(run, run)).toMatchObject({ identical: true, differing_events: 0 });
        expect(compareReplayRuns(run, changed)).toMatchObject({ identical: false, differing_events: 1, first_divergence: { index: 2, left_type: 'market', right_type: 'market' } });
    });

    it('tracks position state per cursor without mutating events', () => {
        const events = buildReplayEvents(run);
        const openIndex = events.findIndex((event) => event.type === 'position_open');
        const closeIndex = events.findIndex((event) => event.type === 'position_close');
        expect(positionStateAtCursor(events, openIndex).position).toBe(1);
        expect(positionStateAtCursor(events, closeIndex).position).toBe(0);
    });

    it('matches conditional breakpoints on type plus metric threshold', () => {
        const events = buildReplayEvents(run);
        const equity = events.find((event) => event.type === 'equity');
        expect(matchesReplayBreakpoint(equity, { event_type: 'equity', metric: 'equity', operator: '<=', threshold: 99 })).toBe(true);
        expect(matchesReplayBreakpoint(equity, { event_type: 'signal', metric: 'none' })).toBe(false);
        expect(matchesReplayBreakpoint(equity, null)).toBe(false);
    });

    it('keeps fill causality unavailable until a governed fill artifact exists', () => {
        expect(replayFillCausality({ orders: [{ order_id: 'order-1' }] })).toMatchObject({ ordersAvailable: true, fillsAvailable: false, status: 'unavailable' });
        expect(replayFillCausality({ orders: [], fills: [{ fill_id: 'f1' }] }).fillsAvailable).toBe(true);
    });
});
