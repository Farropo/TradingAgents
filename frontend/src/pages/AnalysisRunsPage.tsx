import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { analysisCapability, listAnalyses, startAnalysis } from '../lib/api';

export default function AnalysisRunsPage() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState('NVDA');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const capability = useQuery({ queryKey: ['analysis-capability'], queryFn: analysisCapability });
  const analyses = useQuery({ queryKey: ['analysis-runs'], queryFn: listAnalyses, refetchInterval: 5_000 });
  const start = useMutation({
    mutationFn: () => startAnalysis({ ticker, date }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analysis-runs'] }),
  });

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Analysis Runs</h1>
          <p>Optional automated pipeline. The current recommended workflow is Codex-assisted, without LLM API calls.</p>
        </div>
      </div>
      <section className="notice action-notice">
        <div>
          <strong>Modo atual: Codex-assisted sem API calls.</strong>
          <span> Gera o bundle local, cola nesta thread Codex, e importa a resposta para auditoria/ledger.</span>
          {capability.data?.message ? <p>{capability.data.message}</p> : null}
        </div>
        <Link className="button secondary" to="/codex">Open Codex Assisted</Link>
      </section>
      <section className="panel">
        <h2>Start run</h2>
        <div className="form-grid">
          <label>
            Ticker
            <input value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} />
          </label>
          <label>
            Date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          <button onClick={() => start.mutate()} disabled={start.isPending || !capability.data?.normal_available}>
            {start.isPending ? 'Starting...' : capability.data?.normal_available ? 'Start analysis' : 'Requires backend API key'}
          </button>
        </div>
        {capability.data && !capability.data.normal_available ? (
          <p className="muted">
            Selected provider: {capability.data.selected_provider}. Missing backend env: {capability.data.missing_env.join(', ') || 'n/a'}.
          </p>
        ) : null}
        {start.error ? <p className="error">{cleanError(String(start.error))}</p> : null}
      </section>
      <section className="panel">
        <h2>Runs</h2>
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Ticker</th>
              <th>Date</th>
              <th>Rating</th>
              <th>Report</th>
            </tr>
          </thead>
          <tbody>
            {(analyses.data ?? []).map((run) => (
              <tr key={run.run_id}>
                <td>{run.status}</td>
                <td>{run.ticker}</td>
                <td>{run.date}</td>
                <td>{run.rating ?? ''}</td>
                <td className="path-cell">{run.report_path ?? cleanError(run.error ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function cleanError(error: string) {
  return error.split('\n')[0].split('Traceback')[0].trim();
}
