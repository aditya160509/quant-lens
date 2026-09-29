import { render, screen } from '@testing-library/react';
import TearsheetView from '../TearsheetView';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';

const metric = (value: number | null, unit = 'ratio', methodology = 'verified formula') => ({
    value,
    unit,
    status: value === null ? 'unavailable' : 'observed',
    sample_size: value === null ? 0 : 2,
    methodology,
});

describe('TearsheetView canonical artifact rendering', () => {
    beforeEach(() => {
        const gradient = { addColorStop: jest.fn() };
        jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
            fillRect: jest.fn(), setTransform: jest.fn(), beginPath: jest.fn(), moveTo: jest.fn(), lineTo: jest.fn(),
            closePath: jest.fn(), fill: jest.fn(), stroke: jest.fn(), fillText: jest.fn(), setLineDash: jest.fn(),
            createLinearGradient: jest.fn(() => gradient),
        } as unknown as CanvasRenderingContext2D);
        useStudioWorkspaceStore.setState({ ticker: 'SPY' });
        useStudioResultStore.getState().setData({
            candles: [], signals: [], trades: [], equityCurve: [1, 1.1, 1.05], runId: 'run-123',
            series: { equity_net: [1, 1.1, 1.05], equity_gross: [1, 1.11, 1.06], drawdown: [0, 0, -0.05], exposure: [0, 1, 1], turnover: [0, 1, 0], costs: [0, 0.001, 0] },
            metrics: { canonical: {
                total_return: metric(0.1, 'decimal', 'ending equity / starting equity - 1'),
                sharpe: metric(1.2), max_drawdown: metric(0, 'decimal'), hit_rate: metric(null, 'decimal'),
                total_trades: metric(0, 'count'), annual_return: metric(0.2, 'decimal_annualized'), calmar: metric(null),
                average_win: metric(null, 'decimal'), average_loss: metric(null, 'decimal'), payoff: metric(null),
                sortino: metric(1.4), expectancy: metric(null, 'decimal'), max_win: metric(null, 'decimal'),
                max_loss: metric(null, 'decimal'), volatility: metric(0.15, 'decimal_annualized'),
            } },
            metadata: {
                warnings: [{ code: 'METRICS_UNAVAILABLE', message: 'Some metrics unavailable' }],
                provenance: { engine_version: 'studio-metrics/1.0.0', code_hash: 'abc' },
                data_quality: { currency: 'USD', calendar: 'XNYS' },
            },
            volumeProfile: [], mcData: null, wfData: null,
        });
    });

    afterEach(() => jest.restoreAllMocks());

    it('shows canonical values, lineage, warnings, and no invented verdict', () => {
        render(<TearsheetView />);

        expect(screen.getByText('+10.00%')).toBeInTheDocument();
        expect(screen.getByText('run-123')).toBeInTheDocument();
        expect(screen.getByText(/studio-metrics\/1.0.0/)).toBeInTheDocument();
        expect(screen.getByText('1 warning')).toBeInTheDocument();
        expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
        expect(screen.queryByText('Alpha Shield')).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Export canonical results as CSV' })).toBeInTheDocument();
        expect(screen.getByRole('region', { name: 'Observed return diagnostics' })).toBeInTheDocument();
        expect(screen.getByText(/Regime attribution unavailable/)).toBeInTheDocument();
        expect(screen.getByRole('region', { name: 'Supported attribution' })).toBeInTheDocument();
        expect(screen.getByText(/Factor, sector, and multi-asset attribution unavailable/)).toBeInTheDocument();
    });
});
