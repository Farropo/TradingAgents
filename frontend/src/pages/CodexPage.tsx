import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Bot, Copy } from 'lucide-react';
import { createCodexBundle, importCodexResponse, listCodexAnalyses, type CodexBundle } from '../lib/api';

export default function CodexPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [ticker, setTicker] = useState((searchParams.get('ticker') || 'NVDA').toUpperCase());
  const [date, setDate] = useState(searchParams.get('date') || new Date().toISOString().slice(0, 10));
  const [bundle, setBundle] = useState<CodexBundle | null>(null);
  const [responseText, setResponseText] = useState('');

  useEffect(() => {
    const queryTicker = searchParams.get('ticker');
    const queryDate = searchParams.get('date');
    if (queryTicker) setTicker(queryTicker.toUpperCase());
    if (queryDate) setDate(queryDate);
  }, [searchParams]);

  const analyses = useQuery({ queryKey: ['codex-analyses'], queryFn: listCodexAnalyses });
  const prepare = useMutation({
    mutationFn: () => createCodexBundle({ ticker, date, include_fundamentals: true }),
    onSuccess: setBundle,
  });
  const importMutation = useMutation({
    mutationFn: () => importCodexResponse(bundle!.bundle_id, responseText),
    onSuccess: async () => {
      setResponseText('');
      await queryClient.invalidateQueries({ queryKey: ['codex-analyses'] });
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Codex Assisted</h1>
          <p>Generate a no-API prompt bundle, paste it into Codex, then import the response.</p>
        </div>
      </div>
      <section className="panel">
        <h2><Bot size={18} /> Prepare bundle</h2>
        <div className="form-grid">
          <label>
            Ticker
            <input value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} />
          </label>
          <label>
            Date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          <button onClick={() => prepare.mutate()} disabled={prepare.isPending}>
            {prepare.isPending ? 'Preparing...' : 'Prepare bundle'}
          </button>
        </div>
        {prepare.error ? <p className="error">{String(prepare.error)}</p> : null}
      </section>
      {bundle ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>Prompt bundle</h2>
            <button className="secondary" onClick={() => navigator.clipboard?.writeText(bundle.prompt)}>
              <Copy size={16} /> Copy prompt
            </button>
          </div>
          <p className="muted">Bundle ID: {bundle.bundle_id}</p>
          <textarea className="prompt-box" readOnly value={bundle.prompt} />
          <label>
            Paste Codex response
            <textarea value={responseText} onChange={(event) => setResponseText(event.target.value)} rows={10} />
          </label>
          <button onClick={() => importMutation.mutate()} disabled={!responseText || importMutation.isPending}>
            {importMutation.isPending ? 'Importing...' : 'Import response'}
          </button>
          {importMutation.data ? <p className="success">Imported rating: {importMutation.data.rating}</p> : null}
          {importMutation.error ? <p className="error">{String(importMutation.error)}</p> : null}
        </section>
      ) : null}
      <section className="panel">
        <h2>Imported analyses</h2>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Ticker</th>
              <th>Rating</th>
              <th>Report</th>
            </tr>
          </thead>
          <tbody>
            {(analyses.data ?? []).map((item) => (
              <tr key={item.analysis_id}>
                <td>{item.trade_date}</td>
                <td>{item.ticker}</td>
                <td>{item.rating}</td>
                <td className="path-cell">{item.report_path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
