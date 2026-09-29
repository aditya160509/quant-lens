import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ComposerView from '../ComposerView';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { studioRequest } from '@/lib/studioApi';

jest.mock('@/lib/studioApi', () => ({ studioRequest: jest.fn() }));
const request = studioRequest as jest.Mock;

describe('ComposerView', () => {
  beforeEach(() => {
    useStudioResultStore.getState().resetResults();
    request.mockReset();
    request.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === '/reports/recipes' && options?.method === 'POST') return Promise.resolve({ recipe: { recipe_id: 'recipe-1' } });
      if (path === '/reports/recipes') return Promise.resolve({ recipes: [] });
      if (path === '/reports/notes') return Promise.resolve({ notes: [] });
      if (path === '/reports/recipes/recipe-1/render') return Promise.resolve({ report: {
        recipe_id: 'recipe-1', name: 'Allocation review', template: 'portfolio_review', report_hash: 'hash-1',
        blocks: [{ block_id: 'block-1', kind: 'artifact', title: 'Allocation', text: '', layout: { w: 6 }, resolved: { reference: { type: 'portfolio_version', id: 'pfv-1' }, metrics: { 'portfolio.metrics.sharpe': 1.25 }, artifact_hash: 'artifact-hash' } }],
      } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });
  });

  it('starts without fabricated report values', async () => {
    render(<ComposerView />);
    await waitFor(() => expect(request).toHaveBeenCalledWith('/reports/recipes'));
    expect(screen.getByText('Save the recipe to resolve its referenced evidence.')).toBeInTheDocument();
    expect(screen.queryByText('1.25')).not.toBeInTheDocument();
  });

  it('saves reference-only blocks and renders server-resolved metrics', async () => {
    useStudioResultStore.setState({ portfolioVersion: { version_id: 'pfv-1' } });
    render(<ComposerView />);
    fireEvent.change(screen.getByLabelText('Output recipe name'), { target: { value: 'Allocation review' } });
    fireEvent.change(screen.getByLabelText('Report template'), { target: { value: 'portfolio_review' } });
    fireEvent.change(screen.getByLabelText('Block 1 title'), { target: { value: 'Allocation' } });
    fireEvent.change(screen.getByLabelText('Block 1 metric paths'), { target: { value: 'portfolio.metrics.sharpe' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save and render' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('/reports/recipes', expect.objectContaining({
      method: 'POST',
      body: expect.objectContaining({ blocks: [expect.objectContaining({ reference: { type: 'portfolio_version', id: 'pfv-1' }, metric_paths: ['portfolio.metrics.sharpe'] })] }),
    })));
    expect(await screen.findByText('1.25')).toBeInTheDocument();
    expect(screen.getByText('Report hash-1')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'html' })).toHaveAttribute('href', '/api/studio/reports/recipes/recipe-1/export/html');
  });

  it('links artifact selections across blocks sharing one artifact', async () => {
    useStudioResultStore.setState({ portfolioVersion: { version_id: 'pfv-1' } });
    request.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === '/reports/recipes' && options?.method === 'POST') return Promise.resolve({ recipe: { recipe_id: 'recipe-1' } });
      if (path === '/reports/recipes') return Promise.resolve({ recipes: [] });
      if (path === '/reports/notes') return Promise.resolve({ notes: [] });
      if (path === '/reports/recipes/recipe-1/render') return Promise.resolve({ report: {
        recipe_id: 'recipe-1', name: 'Linked review', template: 'custom', report_hash: 'hash-2', warnings: [], formulas: {},
        blocks: [
          { block_id: 'block-1', kind: 'artifact', title: 'First', text: '', layout: { w: 6 }, resolved: { reference: { type: 'portfolio_version', id: 'pfv-1' }, metrics: { 'portfolio.metrics.sharpe': 1.25 }, artifact_hash: 'artifact-hash' } },
          { block_id: 'block-2', kind: 'artifact', title: 'Second', text: '', layout: { w: 6 }, resolved: { reference: { type: 'portfolio_version', id: 'pfv-1' }, metrics: { 'portfolio.metrics.volatility': 0.2 }, artifact_hash: 'artifact-hash' } },
        ],
      } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });
    render(<ComposerView />);
    fireEvent.change(screen.getByLabelText('Output recipe name'), { target: { value: 'Linked review' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save and render' }));
    await screen.findByText('Second');
    fireEvent.click(screen.getByLabelText('Link block 1 artifact'));
    expect(screen.getByLabelText('Link block 1 artifact')).toHaveTextContent('Linked');
    const linked = screen.getAllByText('Second')[0].closest('section');
    expect(linked).toHaveAttribute('data-linked', 'true');
  });

  it('applies a server template layout without inventing metrics', async () => {
    useStudioResultStore.setState({ portfolioVersion: { version_id: 'pfv-1' } });
    request.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === '/reports/recipes') return Promise.resolve({ recipes: [] });
      if (path === '/reports/notes') return Promise.resolve({ notes: [] });
      if (path === '/reports/templates/validation') return Promise.resolve({ template: { name: 'validation', blocks: [
        { block_id: 'validation_evidence', kind: 'artifact', title: 'Out-of-sample evidence', reference: null, metric_paths: ['summary.avgOosSharpe'], text: '', citations: [], layout: { w: 6, h: 4 } },
      ] } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });
    render(<ComposerView />);
    fireEvent.change(screen.getByLabelText('Report template'), { target: { value: 'validation' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply template layout' }));
    await waitFor(() => expect(request).toHaveBeenCalledWith('/reports/templates/validation'));
    expect(screen.getByLabelText('Block 1 metric paths')).toHaveValue('summary.avgOosSharpe');
    expect(screen.queryByText('1.25')).not.toBeInTheDocument();
  });
});
