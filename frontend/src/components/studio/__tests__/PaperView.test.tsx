import { vi, describe, it, expect, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PaperView from '../PaperView';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { studioRequest } from '@/lib/studioApi';

vi.mock('@/lib/studioApi', () => ({ studioRequest: vi.fn() }));
const request = studioRequest as ReturnType<typeof vi.fn>;

describe('PaperView', () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation((path: string) => {
      if (path === '/paper/deployments') return Promise.resolve({ deployments: [] });
      return Promise.reject(new Error(`unexpected ${path}`));
    });
    useStudioResultStore.getState().resetResults();
  });

  it('shows no fabricated deployments or events and keeps promotion gated', async () => {
    render(<PaperView />);
    expect(await screen.findByText('No paper events recorded.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create armed deployment' })).toBeDisabled();
    expect(screen.getByText(/Requires the exact saved portfolio version/)).toBeInTheDocument();
    expect(screen.queryByText('paper-user-1')).not.toBeInTheDocument();
  });

  it('creates from the exact version, validation, and promotion identities', async () => {
    useStudioResultStore.setState({
      portfolioVersion: { version_id: 'pfv-1' },
      portfolioArtifact: { artifact_id: 'portfolio-1' },
      wfJob: { job_id: 'wf-1', status: 'completed' },
      promotionAuditRecords: [{ audit_id: 'audit-1', job_id: 'wf-1', action: 'promote' }],
    });
    request.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === '/paper/deployments' && options?.method === 'POST') return Promise.resolve({ deployment: { deployment_id: 'paper-1' } });
      if (path === '/paper/deployments') return Promise.resolve({ deployments: [] });
      if (path === '/paper/deployments/paper-1') return Promise.resolve({ deployment: { deployment_id: 'paper-1', state: 'armed', kill_switch: { engaged: false } } });
      if (path.endsWith('/events')) return Promise.resolve({ events: [] });
      if (path.endsWith('/reconciliation')) return Promise.resolve({ reconciliation: { fills: [], summary: { fill_count: 0, classified_fill_count: 0, alert_count: 0, mean_slippage_bps: null } } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });
    render(<PaperView />);
    fireEvent.change(screen.getByLabelText('Paper deployment name'), { target: { value: 'Desk route' } });
    fireEvent.change(screen.getByLabelText('Paper universe'), { target: { value: 'SPY,TLT' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create armed deployment' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('/paper/deployments', expect.objectContaining({
      method: 'POST',
      body: expect.objectContaining({ source_version_id: 'pfv-1', validation_job_id: 'wf-1', promotion_audit_id: 'audit-1', universe: ['SPY', 'TLT'] }),
    })));
  });
});
