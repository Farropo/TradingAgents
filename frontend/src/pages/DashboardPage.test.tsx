import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/render';
import DashboardPage from './DashboardPage';

vi.mock('../lib/api', () => ({
  dashboard: async () => ({
    ledger_events: 3,
    decisions: 2,
    codex_analyses: 1,
    fiscal_review_rows_current_year: 4,
    current_year: 2026,
  }),
  listLedgerEvents: async () => [
    { timestamp: '2026-01-01T00:00:00Z', symbol: 'AAPL', side: 'BUY', event_type: 'TRADE', quantity: '1', requires_review: false, source_hash: 'a' },
  ],
  listCodexAnalyses: async () => [
    { analysis_id: 'c1', trade_date: '2026-04-30', ticker: 'NVDA', rating: 'Hold', model_hint: 'GPT-5.5 extra reasoning', report_path: 'r' },
  ],
}));

describe('DashboardPage', () => {
  it('renders local metrics and fiscal notice', async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText('Ledger events')).toBeInTheDocument();
    expect(await screen.findByText('3')).toBeInTheDocument();
    expect(screen.getByText(/Nada é submetido automaticamente/)).toBeInTheDocument();
    expect(await screen.findByText('NVDA')).toBeInTheDocument();
  });
});
