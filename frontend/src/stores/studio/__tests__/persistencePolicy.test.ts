import { persistAlgorithmDraft } from '../algorithmLabStore';
import { persistCompositionDraft } from '../portfolioCompositionStore';
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

    it('keeps algorithm drafts but excludes output and run history', () => {
        const cells = [{ id: 'cell-1', code: 'print(1)' }];
        const persisted = persistAlgorithmDraft({
            sessionId: 'session-1',
            activeCellId: 'cell-1',
            cells,
            output: { stdout: '1' },
            runHistory: [{ id: 'run-1' }],
        });

        expect(persisted).toEqual({ sessionId: 'session-1', activeCellId: 'cell-1', cells });
        expect(persisted).not.toHaveProperty('runHistory');
    });

    it('keeps composition inputs but excludes the server composition', () => {
        const persisted = persistCompositionDraft({
            strategyIds: ['s1', 's2'],
            scheme: 'equal_weight',
            name: 'Book',
            customAllocator: '',
            composition: { composition_id: 'server-result' },
        });

        expect(persisted).toEqual({
            strategyIds: ['s1', 's2'],
            scheme: 'equal_weight',
            name: 'Book',
            customAllocator: '',
        });
        expect(persisted).not.toHaveProperty('composition');
    });
});
