import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/render';
import MarketsPage from './MarketsPage';

const marketMovers = vi.fn(async (_market: 'pt' | 'us' | 'all') => ({
  market: 'pt',
  generated_at: '2026-04-30T00:00:00Z',
  source: 'yfinance',
  quotes: [
    {
      symbol: 'EDP.LS',
      name: 'EDP',
      market: 'pt',
      currency: 'EUR',
      price: 4,
      previous_close: 3.5,
      change: 0.5,
      change_percent: 14.28,
      volume: 1000,
      as_of: '2026-04-29T00:00:00Z',
      source: 'yfinance',
      status: 'ok',
    },
    {
      symbol: 'GALP.LS',
      name: 'Galp',
      market: 'pt',
      currency: 'EUR',
      price: 19,
      previous_close: 20,
      change: -1,
      change_percent: -5,
      volume: 2000,
      as_of: '2026-04-29T00:00:00Z',
      source: 'yfinance',
      status: 'ok',
    },
  ],
  top_gainers: [
    {
      symbol: 'EDP.LS',
      market: 'pt',
      currency: 'EUR',
      price: 4,
      change: 0.5,
      change_percent: 14.28,
      source: 'yfinance',
      status: 'ok',
    },
  ],
  top_losers: [
    {
      symbol: 'GALP.LS',
      market: 'pt',
      currency: 'EUR',
      price: 19,
      change: -1,
      change_percent: -5,
      source: 'yfinance',
      status: 'ok',
    },
  ],
}));

const marketTicker = vi.fn(async (_symbol: string) => ({
  symbol: 'EDP.LS',
  quote: {
    symbol: 'EDP.LS',
    name: 'EDP',
    market: 'pt',
    currency: 'EUR',
    price: 4,
    previous_close: 3.5,
    change: 0.5,
    change_percent: 14.28,
    volume: 1000,
    as_of: '2026-04-29T00:00:00Z',
    source: 'yfinance',
    status: 'ok',
  },
  history: [{ date: '2026-04-29T00:00:00Z', close: 4, volume: 1000 }],
  ledger: {
    event_count: 2,
    net_quantity: '8',
    buy_quantity: '10',
    sell_quantity: '2',
  },
  decisions: [{ id: 1, ticker: 'EDP.LS', trade_date: '2026-04-30', rating: 'Hold' }],
}));

vi.mock('../lib/api', () => ({
  marketMovers: (market: 'pt' | 'us' | 'all') => marketMovers(market),
  marketTicker: (symbol: string) => marketTicker(symbol),
}));

describe('MarketsPage', () => {
  it('renders movers, opens ticker detail, and links to Codex Assisted', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MarketsPage />);

    expect(await screen.findByRole('heading', { name: 'Markets' })).toBeInTheDocument();
    const edpMatches = await screen.findAllByText('EDP.LS');
    expect(edpMatches[0]).toBeInTheDocument();

    await user.click(edpMatches[0]);

    expect(await screen.findByText('EDP.LS detail')).toBeInTheDocument();
    expect(await screen.findByText('Net quantity')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /prepare codex bundle/i })).toHaveAttribute(
      'href',
      '/codex?ticker=EDP.LS&date=2026-04-29',
    );
  });
});
