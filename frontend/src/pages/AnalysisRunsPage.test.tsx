import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/render';
import AnalysisRunsPage from './AnalysisRunsPage';

vi.mock('../lib/api', () => ({
  analysisCapability: async () => ({
    normal_available: false,
    selected_provider: 'openai',
    missing_env: ['OPENAI_API_KEY'],
    message: 'Use Codex Assisted for the no-API workflow.',
    recommended_mode: 'codex-assisted',
  }),
  listAnalyses: async () => [
    {
      run_id: 'run-1',
      status: 'failed',
      ticker: 'NVDA',
      date: '2026-04-30',
      error: 'Missing key\nTraceback should not be shown',
    },
  ],
  startAnalysis: async () => {
    throw new Error('should not start');
  },
}));

describe('AnalysisRunsPage', () => {
  it('points users to Codex-assisted mode when no backend API key exists', async () => {
    renderWithProviders(<AnalysisRunsPage />);

    expect(await screen.findByText(/Modo atual: Codex-assisted sem API calls/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /requires backend api key/i })).toBeDisabled();
    expect(screen.getByRole('link', { name: /open codex assisted/i })).toHaveAttribute('href', '/codex');
    expect(await screen.findByText('Missing key')).toBeInTheDocument();
    expect(screen.queryByText(/Traceback should not be shown/i)).not.toBeInTheDocument();
  });
});
