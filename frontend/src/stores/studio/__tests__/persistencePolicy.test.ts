import { describe, it, expect } from "vitest";
import { persistDataStudioDraft } from '../dataStudioStore';

describe('Studio browser persistence policy', () => {
    it('keeps data query preferences but excludes fetched series', () => {
        const persisted = persistDataStudioDraft({
            ticker: 'SPY',
            request: { tickers: ['SPY'] },
            series: { rows: [1, 2] },
            seriesByTicker: { SPY: { rows: [1, 2] } },
        });

        expect(persisted).toEqual({ ticker: 'SPY', request: { tickers: ['SPY'] } });
        expect(persisted).not.toHaveProperty('seriesByTicker');
    });

});
