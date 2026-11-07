import { fireEvent, render, screen } from '@testing-library/react';
import StudioModeStage from '../shell/StudioModeStage';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';

vi.mock('../DevelopView', () => ({ default: function MockDevelop() { return <div>Develop surface</div>; } }));
vi.mock('../TearsheetView', () => ({ default: function MockResults() { return <div>Results surface</div>; } }));
vi.mock('../ReplayView', () => ({ default: function MockReplay() { return <div>Replay surface</div>; } }));
vi.mock('../ValidateView', () => ({ default: function MockValidate() { return <div>Walk-forward workflow</div>; } }));
vi.mock('../StressView', () => ({ default: function MockStress() { return <div>Monte Carlo workflow</div>; } }));
vi.mock('../StudioPaneBoundary', () => ({ default: ({ children }: { children: React.ReactNode }) => children }));

describe('StudioModeStage', () => {
  beforeEach(() => useStudioWorkspaceStore.setState({ activeTab: 'validate' }));

  it('keeps walk-forward and Monte Carlo workflows inside one Validate mode', async () => {
    render(<StudioModeStage />);

    expect(await screen.findByText('Walk-forward workflow')).toBeInTheDocument();
    expect(screen.queryByText('Monte Carlo workflow')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Monte Carlo stress' }));
    expect(await screen.findByText('Monte Carlo workflow')).toBeInTheDocument();
    expect(screen.queryByText('Walk-forward workflow')).not.toBeInTheDocument();
  });
});
