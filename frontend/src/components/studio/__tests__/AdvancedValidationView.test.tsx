import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdvancedValidationView from '../AdvancedValidationView';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { studioRequest } from '@/lib/studioApi';

vi.mock('@/lib/studioApi', () => ({ studioRequest: vi.fn() }));
const request = studioRequest as ReturnType<typeof vi.fn>;

describe('AdvancedValidationView', () => {
  beforeEach(() => {
    request.mockReset();
    useStudioResultStore.getState().resetResults();
  });

  it('does not display evidence before an explicit user run', () => {
    render(<AdvancedValidationView />);
    expect(screen.getByText('Advanced evidence')).toBeInTheDocument();
    expect(screen.queryByText('Deflated probability')).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });

  it('submits observed portfolio returns and user trial count', async () => {
    useStudioResultStore.setState({ portfolioArtifact: { observed_portfolio_returns: Array.from({ length: 40 }, (_, index) => index % 2 ? -0.001 : 0.002) } });
    request.mockResolvedValue({ evidence: {
      annualized_sharpe: 1.1, probabilistic_sharpe_probability: 0.92,
      deflated_sharpe_probability: 0.71,
      selection_bias: { expected_max_null_annualized_sharpe: 0.4 },
    } });
    render(<AdvancedValidationView />);
    fireEvent.change(screen.getByLabelText('Strategy trials'), { target: { value: '25' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Run' })[0]);
    await waitFor(() => expect(request).toHaveBeenCalledWith('/validation/advanced/sharpe', expect.objectContaining({
      method: 'POST', body: expect.objectContaining({ trials: 25, returns: expect.any(Array) }),
    })));
    expect(await screen.findByText('Deflated probability')).toBeInTheDocument();
    expect(screen.getByText('71.00%')).toBeInTheDocument();
  });
});
