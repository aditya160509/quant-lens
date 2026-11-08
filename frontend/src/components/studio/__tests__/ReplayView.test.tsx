import { vi, describe, it, expect, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReplayView from '../ReplayView';
import { getStudioJob } from '@/lib/studioApi';
import { useStudioResultStore } from '@/stores/studio/resultStore';

vi.mock('@/lib/studioApi', () => ({ getStudioJob: vi.fn() }));
vi.mock('../results/VirtualTradeLedger', () => ({
    __esModule: true,
    default: () => <div>trade ledger</div>,
    tradeReturn: (trade: { pnl?: number }) => trade.pnl ?? null,
}));

const executionResult = {
    status: 'success',
    candles: [{ time: 1, open: 100, high: 102, low: 99, close: 101, volume: 1000 }],
    metadata: { data_quality: { currency: 'USD', calendar: 'XNYS', source: 'market_universe_daily' }, provenance: { dataset_id: 'market_universe_daily', engine_version: 'studio/1', parameters: { return_convention: 'simple_returns_compounded_to_net_equity' } } },
    signals: [{ date: '1970-01-01T00:00:01.000Z', timestamp: 1000, direction: 1, price: 101, idx: 0 }],
    trades: [],
    equity_curve: [1, 1.01],
    metrics: {},
};

describe('ReplayView persisted deep links', () => {
    beforeEach(() => {
        useStudioResultStore.getState().resetResults();
        window.history.replaceState(null, '', '/studio?run=run-1&event=signal%3A0');
        vi.mocked(getStudioJob).mockResolvedValue({ job_id: 'run-1', status: 'completed', result: executionResult });
    });

    it('loads and validates the persisted execution artifact without rerunning it', async () => {
        render(<ReplayView />);

        await waitFor(() => expect(getStudioJob).toHaveBeenCalledWith('run-1', expect.objectContaining({ signal: expect.any(AbortSignal) })));
        await waitFor(() => expect(useStudioResultStore.getState().data.runId).toBe('run-1'));
        expect(screen.getByText(/Run run-1/)).toBeInTheDocument();
        expect(screen.getByText('signal')).toBeInTheDocument();
        expect(window.location.search).toContain('event=signal%3A0');
        expect(window.location.search).toContain('time=1000');
    });

    it('compares two compatible persisted event streams without executing code', async () => {
        render(<ReplayView />);
        await waitFor(() => expect(useStudioResultStore.getState().data.runId).toBe('run-1'));
        vi.mocked(getStudioJob).mockResolvedValueOnce({ job_id: 'run-2', status: 'completed', result: { ...executionResult, candles: [{ ...executionResult.candles[0], close: 99 }] } });

        fireEvent.change(screen.getByRole('textbox', { name: 'Comparison run ID' }), { target: { value: 'run-2' } });
        fireEvent.click(screen.getByRole('button', { name: 'Compare' }));

        expect(await screen.findByText(/Compared with run-2: 1 differing events/)).toBeInTheDocument();
        expect(getStudioJob).toHaveBeenLastCalledWith('run-2');
    });

    it('replays the deterministic portfolio construction artifact without inventing fills', () => {
        window.history.replaceState(null, '', '/studio?mode=replay');
        useStudioResultStore.setState({ portfolioArtifact: {
            artifact_id: 'portfolio_0123456789abcdef', engine_version: 'studio-portfolio-1.0', objective: 'min_variance',
            model: { covariance: 'sample' }, constraints: { gross_leverage: 1 }, constraint_exposures: [],
            metrics: { volatility: 0.1 }, assets: ['SPY', 'TLT'], current_weights: { SPY: 0.5, TLT: 0.5 },
            weights: { SPY: 0.4, TLT: 0.6 }, trades: { SPY: -0.1, TLT: 0.1 }, risk_contribution: { SPY: 0.6, TLT: 0.4 }, scenario_results: [],
        } });
        render(<ReplayView />);
        expect(screen.getByText('Portfolio artifact replay')).toBeInTheDocument();
        expect(screen.getByText('SPY target')).toBeInTheDocument();
        expect(screen.queryByText(/fill/i)).not.toBeInTheDocument();
    });
});
