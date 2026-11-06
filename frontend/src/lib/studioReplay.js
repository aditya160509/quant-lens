const EVENT_ORDER = { market: 0, signal: 1, position_open: 2, equity: 3, position_close: 4 };

const timestampOf = (value) => {
    if (Number.isFinite(value)) return value < 1e12 ? value * 1000 : value;
    const parsed = value ? Date.parse(value) : Number.NaN;
    return Number.isFinite(parsed) ? parsed : null;
};

const immutableEvent = (event) => Object.freeze({
    ...event,
    causal_event_ids: Object.freeze([...(event.causal_event_ids || [])]),
    payload: Object.freeze({ ...(event.payload || {}) }),
});

/**
 * Build an ordered, read-only replay stream from one returned execution artifact.
 * No strategy logic is rerun and no absent order/fill event is synthesized.
 */
export function buildReplayEvents(run) {
    if (!run || typeof run !== 'object') return Object.freeze([]);
    const events = [];
    const signalsByDate = new Map();

    (run.candles || []).forEach((candle, sourceIndex) => {
        const timestamp = timestampOf(candle.time);
        if (timestamp === null) return;
        events.push({
            event_id: `market:${sourceIndex}`,
            type: 'market',
            timestamp,
            source_index: sourceIndex,
            causal_event_ids: [],
            payload: { open: candle.open, high: candle.high, low: candle.low, close: candle.close, volume: candle.volume },
        });
    });

    (run.signals || []).forEach((signal, sourceIndex) => {
        const timestamp = timestampOf(signal.timestamp ?? signal.date);
        if (timestamp === null) return;
        const eventId = `signal:${sourceIndex}`;
        const event = {
            event_id: eventId,
            type: 'signal',
            timestamp,
            source_index: sourceIndex,
            causal_event_ids: [],
            payload: { direction: signal.direction, price: signal.price, confidence: signal.confidence, momentum: signal.momentum, bar_index: signal.idx },
        };
        events.push(event);
        if (signal.date) signalsByDate.set(signal.date, eventId);

        const equity = run.series?.equity_net?.[sourceIndex + 1] ?? run.equityCurve?.[sourceIndex + 1];
        if (Number.isFinite(equity)) {
            events.push({
                event_id: `equity:${sourceIndex}`,
                type: 'equity',
                timestamp,
                source_index: sourceIndex,
                causal_event_ids: [eventId],
                payload: { equity },
            });
        }
    });

    (run.trades || []).forEach((trade, sourceIndex) => {
        const entryTimestamp = timestampOf(trade.entry_date);
        const exitTimestamp = timestampOf(trade.exit_date);
        const entryCause = signalsByDate.get(trade.entry_date);
        const exitCause = signalsByDate.get(trade.exit_date);
        const openId = `position_open:${sourceIndex}`;
        if (entryTimestamp !== null) {
            events.push({
                event_id: openId,
                type: 'position_open',
                timestamp: entryTimestamp,
                source_index: sourceIndex,
                causal_event_ids: entryCause ? [entryCause] : [],
                payload: { direction: trade.direction, price: trade.entry_price },
            });
        }
        if (exitTimestamp !== null) {
            events.push({
                event_id: `position_close:${sourceIndex}`,
                type: 'position_close',
                timestamp: exitTimestamp,
                source_index: sourceIndex,
                causal_event_ids: [openId, ...(exitCause ? [exitCause] : [])],
                payload: { price: trade.exit_price, net_return: trade.pnl_pct ?? trade.pnl, mae: trade.mae, mfe: trade.mfe, holding_period: trade.holding_period },
            });
        }
    });

    events.sort((left, right) => left.timestamp - right.timestamp
        || (EVENT_ORDER[left.type] ?? 99) - (EVENT_ORDER[right.type] ?? 99)
        || left.source_index - right.source_index);
    return Object.freeze(events.map((event, orderedIndex) => immutableEvent({ ...event, ordered_index: orderedIndex })));
}

export const replayEventTypes = Object.freeze(['market', 'signal', 'position_open', 'equity', 'position_close']);

export function positionStateAtCursor(events, cursor) {
    let position = 0;
    let entryPrice = null;
    let entryEventId = null;
    const limit = Math.max(0, Math.min(cursor + 1, events.length));
    for (let index = 0; index < limit; index += 1) {
        const event = events[index];
        if (event.type === 'position_open') {
            position = event.payload.direction === -1 ? -1 : 1;
            entryPrice = Number.isFinite(event.payload.price) ? event.payload.price : null;
            entryEventId = event.event_id;
        } else if (event.type === 'position_close') {
            position = 0;
            entryPrice = null;
            entryEventId = null;
        } else if (event.type === 'signal' && Number.isFinite(event.payload.direction)) {
            if (event.payload.direction !== 0 && event.payload.direction !== position) {
                position = event.payload.direction > 0 ? 1 : -1;
                entryPrice = Number.isFinite(event.payload.price) ? event.payload.price : entryPrice;
                entryEventId = event.event_id;
            }
        }
    }
    return Object.freeze({ position, entry_price: entryPrice, entry_event_id: entryEventId, events_observed: limit });
}

export function matchesReplayBreakpoint(event, predicate) {
    if (!predicate || typeof predicate !== 'object') return false;
    if (predicate.event_type && predicate.event_type !== 'any' && event.type !== predicate.event_type) return false;
    const metricValue = event.payload?.[predicate.metric];
    if (predicate.metric && predicate.metric !== 'none') {
        if (!Number.isFinite(metricValue) || !Number.isFinite(predicate.threshold)) return false;
        if (predicate.operator === '<=' && !(metricValue <= predicate.threshold)) return false;
        if (predicate.operator === '>=' && !(metricValue >= predicate.threshold)) return false;
        if (!['<=', '>='].includes(predicate.operator)) return false;
        return true;
    }
    return Boolean(predicate.event_type && predicate.event_type !== 'any');
}

export function replayFillCausality(run) {
    const ordersAvailable = Array.isArray(run?.orders) && run.orders.length > 0;
    const fillsAvailable = Array.isArray(run?.fills) && run.fills.length > 0;
    return Object.freeze({
        ordersAvailable,
        fillsAvailable,
        status: fillsAvailable ? 'observed' : 'unavailable',
        reason: fillsAvailable
            ? 'Fill events link to their causal order and signal events.'
            : 'No governed fill artifact exists; fills are not synthesized and no fill causality is shown.',
    });
}

export function compareReplayRuns(leftRun, rightRun) {
    const left = buildReplayEvents(leftRun);
    const right = buildReplayEvents(rightRun);
    const length = Math.max(left.length, right.length);
    let firstDivergence = null;
    let differingEvents = 0;
    for (let index = 0; index < length; index += 1) {
        const a = left[index];
        const b = right[index];
        const same = Boolean(a && b) && a.type === b.type && a.timestamp === b.timestamp && JSON.stringify(a.payload) === JSON.stringify(b.payload);
        if (!same) {
            differingEvents += 1;
            if (!firstDivergence) firstDivergence = Object.freeze({ index, left_event_id: a?.event_id || null, right_event_id: b?.event_id || null, left_type: a?.type || null, right_type: b?.type || null, timestamp: a?.timestamp ?? b?.timestamp ?? null });
        }
    }
    return Object.freeze({ identical: differingEvents === 0, left_count: left.length, right_count: right.length, differing_events: differingEvents, first_divergence: firstDivergence });
}
