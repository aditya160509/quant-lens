import { fireEvent, render, screen } from '@testing-library/react';
import StudioModeStage from '../shell/StudioModeStage';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';

jest.mock('../DevelopView', () => function MockDevelop() { return <div>Develop surface</div>; });
jest.mock('../TearsheetView', () => function MockResults() { return <div>Results surface</div>; });
jest.mock('../ReplayView', () => function MockReplay() { return <div>Replay surface</div>; });
jest.mock('../ValidateView', () => function MockValidate() { return <div>Walk-forward workflow</div>; });
jest.mock('../StressView', () => function MockStress() { return <div>Monte Carlo workflow</div>; });
jest.mock('../StudioPaneBoundary', () => ({ children }: { children: React.ReactNode }) => children);

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
