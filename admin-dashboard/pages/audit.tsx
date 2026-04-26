import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { apiGet } from '@/lib/api';

interface AuditEntry {
  id: string;
  admin_torn_id: number;
  action: string;
  target_torn_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

interface User {
  torn_id: number;
  torn_name: string;
}

const ACTION_COLOR: Record<string, string> = {
  role_change:        '#47A6FF',
  subscription_edit:  '#73DF5D',
  user_deleted:       '#FF5555',
  ban:                '#FF5555',
};

function fmtDate(s: string): string {
  return new Date(s).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtDetails(details: Record<string, unknown>): string {
  if (!details || Object.keys(details).length === 0) return '—';
  return Object.entries(details)
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(', ');
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [names,   setNames]   = useState<Record<number, string>>({});
  const [error,   setError]   = useState('');
  const [filter,  setFilter]  = useState('');

  useEffect(() => {
    apiGet<AuditEntry[]>('/api/admin/audit-log').then(setEntries).catch(e => setError(e.message));
    apiGet<User[]>('/api/admin/users')
      .then(users => {
        const map: Record<number, string> = {};
        users.forEach(u => { map[u.torn_id] = u.torn_name; });
        setNames(map);
      })
      .catch(() => {});
  }, []);

  const name = (id: number | null) =>
    id == null ? '—' : (names[id] ? `${names[id]} [${id}]` : String(id));

  const filtered = filter
    ? entries.filter(e =>
        e.action.includes(filter) ||
        String(e.admin_torn_id).includes(filter) ||
        String(e.target_torn_id ?? '').includes(filter)
      )
    : entries;

  return (
    <Layout>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#eee' }}>Audit Log ({entries.length})</h2>
        <input
          placeholder="Filter by action or ID…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{
            marginLeft: 'auto', padding: '5px 10px', background: '#1a1a2e',
            border: '1px solid #2a2a4a', borderRadius: 4, color: '#eee', fontSize: 12,
          }}
        />
      </div>

      {error && <div style={{ color: '#FF5555', marginBottom: 12, fontSize: 12 }}>{error}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: '#888', borderBottom: '1px solid #2a2a4a' }}>
              {['Admin', 'Action', 'Target', 'Details', 'Date'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '6px 12px', fontWeight: 'normal' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id} style={{ borderBottom: '1px solid #1a1a30' }}>
                <td style={{ padding: '8px 12px' }}>
                  <a
                    href={`https://www.torn.com/profiles.php?XID=${e.admin_torn_id}`}
                    target="_blank" rel="noreferrer"
                    style={{ color: '#47A6FF', textDecoration: 'none' }}
                  >
                    {name(e.admin_torn_id)}
                  </a>
                </td>
                <td style={{ padding: '8px 12px' }}>
                  <span style={{
                    color: ACTION_COLOR[e.action] ?? '#eee',
                    fontWeight: 'bold',
                  }}>
                    {e.action}
                  </span>
                </td>
                <td style={{ padding: '8px 12px', color: '#888' }}>
                  {e.target_torn_id ? (
                    <a
                      href={`https://www.torn.com/profiles.php?XID=${e.target_torn_id}`}
                      target="_blank" rel="noreferrer"
                      style={{ color: '#aaa', textDecoration: 'none' }}
                    >
                      {name(e.target_torn_id)}
                    </a>
                  ) : '—'}
                </td>
                <td style={{ padding: '8px 12px', color: '#666', fontFamily: 'monospace', fontSize: 11 }}>
                  {fmtDetails(e.details)}
                </td>
                <td style={{ padding: '8px 12px', color: '#555' }}>{fmtDate(e.created_at)}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={5} style={{ padding: '16px 12px', color: '#555' }}>No entries found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
