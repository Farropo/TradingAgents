import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/render';
import CodexPage from './CodexPage';

const createCodexBundle = vi.fn(async (_payload: { ticker: string; date: string; include_fundamentals: boolean }) => ({
  bundle_id: 'bundle-1',
  bundle_dir: 'dir',
  bundle_json_path: 'bundle.json',
  prompt_path: 'prompt.md',
  prompt_hash: 'hash',
  prompt: 'Codex prompt body',
}));
const importCodexResponse = vi.fn(async (_bundleId: string, _responseText: string) => ({
  analysis_id: 'a1',
  analysis_dir: 'dir',
  response_path: 'response.md',
  report_path: 'report.md',
  bundle_hash: 'b',
  response_hash: 'r',
  decision_link_id: 1,
  rating: 'Buy',
}));

vi.mock('../lib/api', () => ({
  createCodexBundle: (payload: { ticker: string; date: string; include_fundamentals: boolean }) => createCodexBundle(payload),
  importCodexResponse: (bundleId: string, responseText: string) => importCodexResponse(bundleId, responseText),
  listCodexAnalyses: async () => [],
}));

describe('CodexPage', () => {
  it('reads ticker and date from query params', () => {
    renderWithProviders(<CodexPage />, '/codex?ticker=EDP.LS&date=2026-04-29');

    expect(screen.getByLabelText(/ticker/i)).toHaveValue('EDP.LS');
    expect(screen.getByLabelText(/date/i)).toHaveValue('2026-04-29');
  });

  it('prepares a bundle and imports a pasted response', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CodexPage />);

    await user.click(screen.getByRole('button', { name: /prepare bundle/i }));
    expect(await screen.findByDisplayValue('Codex prompt body')).toBeInTheDocument();

    await user.type(screen.getByLabelText(/paste codex response/i), '**Rating**: Buy');
    await user.click(screen.getByRole('button', { name: /import response/i }));

    expect(await screen.findByText(/Imported rating: Buy/i)).toBeInTheDocument();
    expect(importCodexResponse).toHaveBeenCalledWith('bundle-1', '**Rating**: Buy');
  });
});
