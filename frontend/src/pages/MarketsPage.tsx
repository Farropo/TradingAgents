import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownRight, ArrowUpRight, BarChart3, ExternalLink } from 'lucide-react';
import { marketMovers, marketTicker, type MarketQuote } from '../lib/api';

type MarketFilter = 'pt' | 'us' | 'all';

const marketTabs: Array<{ id: MarketFilter; label: string }> = [
  { id: 'pt', label: 'Portugal' },
  { id: 'us', label: 'EUA' },
  { id: 'all', label: 'All' },
];

export default function MarketsPage() {
  const [market, setMarket] = useState<MarketFilter>('pt');
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const movers = useQuery({
    queryKey: ['market-movers', market],
    queryFn: () => marketMovers(market),
    refetchInterval: 60_000,
  });
  const detail = useQuery({
    queryKey: ['market-ticker', selectedSymbol],
    queryFn: () => marketTicker(selectedSymbol!),
    enabled: Boolean(selectedSymbol),
  });

  const sortedQuotes = useMemo(
    () => [...(movers.data?.quotes ?? [])].sort((a, b) => a.symbol.localeCompare(b.symbol)),
    [movers.data?.quotes],
  );

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Markets</h1>
          <p>Delayed local watchlists for Portuguese and US tickers. No LLM API calls.</p>
        </div>
      </div>
      <section className="notice">
        <strong>Dados para triagem.</strong>
        <span> Fonte yfinance gratuita/delayed; confirmar no broker antes de executar qualquer ordem.</span>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2><BarChart3 size={18} /> Watchlists</h2>
          <div className="segmented-control" aria-label="Market filter">
            {marketTabs.map((tab) => (
              <button
                className={market === tab.id ? 'active' : 'secondary'}
                key={tab.id}
                onClick={() => {
                  setMarket(tab.id);
                  setSelectedSymbol(null);
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        {movers.isLoading ? <p className="muted">Loading market data...</p> : null}
        {movers.error ? <p className="error">{String(movers.error)}</p> : null}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th>Price</th>
                <th>Change</th>
                <th>Volume</th>
                <th>As of</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sortedQuotes.map((quote) => (
                <QuoteRow
                  key={quote.symbol}
                  quote={quote}
                  selected={selectedSymbol === quote.symbol}
                  onSelect={() => setSelectedSymbol(quote.symbol)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="two-column">
        <section className="panel">
          <h2><ArrowUpRight size={18} /> Top gainers</h2>
          <MoverList quotes={movers.data?.top_gainers ?? []} onSelect={setSelectedSymbol} />
        </section>
        <section className="panel">
          <h2><ArrowDownRight size={18} /> Top losers</h2>
          <MoverList quotes={movers.data?.top_losers ?? []} onSelect={setSelectedSymbol} />
        </section>
      </div>
      {selectedSymbol ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>{selectedSymbol} detail</h2>
            {detail.data ? (
              <Link className="button secondary" to={`/codex?ticker=${encodeURIComponent(selectedSymbol)}&date=${codexDate(detail.data.quote.as_of)}`}>
                <ExternalLink size={16} /> Prepare Codex Bundle
              </Link>
            ) : null}
          </div>
          {detail.isLoading ? <p className="muted">Loading ticker detail...</p> : null}
          {detail.error ? <p className="error">{String(detail.error)}</p> : null}
          {detail.data ? (
            <div className="ticker-detail-grid">
              <div>
                <h3>Quote</h3>
                <dl className="detail-list">
                  <dt>Price</dt>
                  <dd>{formatPrice(detail.data.quote)}</dd>
                  <dt>Change</dt>
                  <dd className={changeClass(detail.data.quote)}>{formatChange(detail.data.quote)}</dd>
                  <dt>Volume</dt>
                  <dd>{formatInteger(detail.data.quote.volume)}</dd>
                  <dt>Source</dt>
                  <dd>{detail.data.quote.source} / {detail.data.quote.status}</dd>
                </dl>
              </div>
              <div>
                <h3>Ledger exposure</h3>
                <dl className="detail-list">
                  <dt>Net quantity</dt>
                  <dd>{detail.data.ledger.net_quantity}</dd>
                  <dt>Buys</dt>
                  <dd>{detail.data.ledger.buy_quantity}</dd>
                  <dt>Sells</dt>
                  <dd>{detail.data.ledger.sell_quantity}</dd>
                  <dt>Events</dt>
                  <dd>{detail.data.ledger.event_count}</dd>
                </dl>
              </div>
              <div>
                <h3>Mini history</h3>
                <div className="mini-history">
                  {detail.data.history.slice(-10).map((point) => (
                    <span key={point.date}>
                      <strong>{formatNumber(point.close)}</strong>
                      <small>{point.date.slice(5, 10)}</small>
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h3>Recent decisions</h3>
                {detail.data.decisions.length ? (
                  <ul className="compact-list">
                    {detail.data.decisions.map((decision) => (
                      <li key={String(decision.id ?? `${decision.ticker}-${decision.trade_date}`)}>
                        <strong>{String(decision.rating ?? 'n/a')}</strong>
                        <span>{String(decision.trade_date ?? '')}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">No imported decisions for this ticker yet.</p>
                )}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function QuoteRow({ quote, selected, onSelect }: { quote: MarketQuote; selected: boolean; onSelect: () => void }) {
  return (
    <tr className={`clickable-row ${selected ? 'selected-row' : ''}`} onClick={onSelect}>
      <td className="mono">{quote.symbol}</td>
      <td>{quote.name ?? ''}</td>
      <td>{formatPrice(quote)}</td>
      <td className={changeClass(quote)}>{formatChange(quote)}</td>
      <td>{formatInteger(quote.volume)}</td>
      <td>{quote.as_of?.slice(0, 10) ?? ''}</td>
      <td><span className={`status-pill ${quote.status}`}>{quote.status}</span></td>
    </tr>
  );
}

function MoverList({ quotes, onSelect }: { quotes: MarketQuote[]; onSelect: (symbol: string) => void }) {
  if (!quotes.length) return <p className="muted">No price changes available.</p>;
  return (
    <ul className="mover-list">
      {quotes.slice(0, 5).map((quote) => (
        <li key={quote.symbol}>
          <button className="link-button" onClick={() => onSelect(quote.symbol)}>
            <span className="mono">{quote.symbol}</span>
            <span className={changeClass(quote)}>{formatPercent(quote.change_percent)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function formatPrice(quote: MarketQuote) {
  if (quote.price == null) return '-';
  return `${formatNumber(quote.price)} ${quote.currency}`;
}

function formatChange(quote: MarketQuote) {
  if (quote.change == null || quote.change_percent == null) return '-';
  return `${formatSigned(quote.change)} (${formatPercent(quote.change_percent)})`;
}

function formatPercent(value?: number | null) {
  if (value == null) return '-';
  return `${formatSigned(value)}%`;
}

function formatSigned(value: number) {
  return `${value > 0 ? '+' : ''}${formatNumber(value)}`;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('pt-PT', { maximumFractionDigits: 3 }).format(value);
}

function formatInteger(value?: number | null) {
  if (value == null) return '-';
  return new Intl.NumberFormat('pt-PT').format(value);
}

function changeClass(quote: MarketQuote) {
  if ((quote.change_percent ?? 0) > 0) return 'positive';
  if ((quote.change_percent ?? 0) < 0) return 'negative';
  return 'muted';
}

function codexDate(asOf?: string | null) {
  return encodeURIComponent(asOf?.slice(0, 10) || new Date().toISOString().slice(0, 10));
}
