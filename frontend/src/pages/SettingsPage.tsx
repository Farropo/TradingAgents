import { useQuery } from '@tanstack/react-query';
import { defaults } from '../lib/api';

export default function SettingsPage() {
  const settings = useQuery({ queryKey: ['defaults'], queryFn: defaults });

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Settings</h1>
          <p>Local paths and backend-only environment status. Secret values are never displayed.</p>
        </div>
      </div>
      <section className="panel">
        <h2>Paths</h2>
        <table>
          <tbody>
            {Object.entries(settings.data?.paths ?? {}).map(([key, value]) => (
              <tr key={key}>
                <th>{key}</th>
                <td className="path-cell">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>LLM runner</h2>
        <table>
          <tbody>
            {Object.entries(settings.data?.llm ?? {}).map(([key, value]) => (
              <tr key={key}>
                <th>{key}</th>
                <td className="path-cell">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Provider environment</h2>
        <table>
          <thead>
            <tr>
              <th>Variable</th>
              <th>Configured</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(settings.data?.env ?? {}).map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{value ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted">{settings.data?.message}</p>
      </section>
    </div>
  );
}
