import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ValidateView from '../ValidateView';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioEditorStore } from '@/stores/studio/editorStore';
import { getPromotionAudit, recordPromotionAudit } from '@/lib/studioApi';

jest.mock('@/hooks/studio/useStudioAnalysis', () => ({ useStudioAnalysis: () => ({ runWalkForward: jest.fn(), cancelWalkForward: jest.fn() }) }));
jest.mock('@/lib/studioApi', () => ({ getPromotionAudit: jest.fn(), recordPromotionAudit: jest.fn() }));

describe('Validate promotion audit', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.mocked(getPromotionAudit).mockResolvedValue({ records: [] });
    jest.mocked(recordPromotionAudit).mockResolvedValue({ audit: { audit_id: 'audit-1', action: 'override', actor: 'risk', rationale: 'reviewed', created_at: '2026-09-22', record_hash: 'abcdef0123456789' } });
    useStudioEditorStore.setState({ codeA: 'strategy' });
    useStudioResultStore.getState().resetResults();
    useStudioResultStore.setState((state) => ({
      wfJob: { job_id: 'wf-1', status: 'completed' },
      data: { ...state.data, equityCurve: Array.from({ length: 120 }, (_, index) => 1 + index / 1000), wfData: { summary: {}, folds: [], verdict: { status: 'PASSED', tests: [], thresholds: {} } } },
    }));
  });

  it('requires attributable rationale and appends the immutable response', async () => {
    render(<ValidateView />);
    await waitFor(() => expect(getPromotionAudit).toHaveBeenCalledWith('wf-1', expect.objectContaining({ signal: expect.any(AbortSignal) })));

    fireEvent.click(screen.getByRole('button', { name: 'override' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Actor and rationale are required');
    fireEvent.change(screen.getByRole('textbox', { name: 'Decision actor' }), { target: { value: 'risk' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Decision rationale' }), { target: { value: 'reviewed' } });
    fireEvent.click(screen.getByRole('button', { name: 'override' }));

    await waitFor(() => expect(recordPromotionAudit).toHaveBeenCalledWith('wf-1', { action: 'override', actor: 'risk', rationale: 'reviewed' }));
    expect((await screen.findAllByText(/override/i)).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/hash abcdef0123456789/i)).toBeInTheDocument();
  });
});
