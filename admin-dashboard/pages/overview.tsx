import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { apiGet } from '@/lib/api';

interface Overview {
  total_users: number;
  training_samples: number;
  cached_predictions: number;
  active_model: {
    version: string;
    mape: number;
    rmse: number;
    training_samples: number;
    created_at: string;
  } | null;
}

interface User {
  torn_id: number;
  torn_name: string;
  role: string;
  subscription_tier: string;
  subscription_end: string | null;
  last_seen: string | null;
  created_at: string;
}

function Card({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{
      background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8,
      padding: '20px 24px', minWidth: 160,
    }}>
      <div style={{ color: '#888', fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{ color: '#eee', fontSize: 28, fontWeight: 'bold' }}>{value}</div>
      {sub && <div style={{ color: '#888', fontSize: 11, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function fmtDate(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function OverviewPage() {
  const [stats, setStats]   = useState<Overview | null>(null);
  const [users, setUsers]   = useState<User[]>([]);
  const [error, setError]   = useState('');

  useEffect(() => {
    apiGet<Overview>('/api/admin/stats/overview')
      .then(setStats)
      .catch(e => setError(e.message));

    apiGet<User[]>('/api/admin/users')
      .then(all => setUsers(all.slice(0, 10)))
      .catch(() => {});
  }, []);

  const model = stats?.active_model;

  return (
    <Layout>
      <h2 style={{ margin: '0 0 24px', color: '#eee' }}>Overview</h2>

      {error && <div style={{ color: '#FF5555', marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 32 }}>
        <Card label="Total users"       value={stats?.total_users         ?? '…'} />
        <Card label="Training samples"  value={stats?.training_samples    ?? '…'} />
        <Card label="Cached predictions" value={stats?.cached_predictions ?? '…'} />
        <Card
          label="Active model"
          value={model ? model.version : 'None'}
          sub={model ? `MAPE ${model.mape.toFixed(1)}%  ·  ${model.training_samples} samples` : undefined}
        />
      </div>

      <h3 style={{ margin: '0 0 12px', color: '#eee', fontSize: 15 }}>Recent signups</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ color: '#888', borderBottom: '1px solid #2a2a4a' }}>
              {['ID', 'Name', 'Role', 'Tier', 'Joined', 'Last seen'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '6px 12px', fontWeight: 'normal' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.torn_id} style={{ borderBottom: '1px solid #1e1e38' }}>
                <td style={{ padding: '8px 12px', color: '#888' }}>{u.torn_id}</td>
                <td style={{ padding: '8px 12px' }}>
                  <a
                    href={`https://www.torn.com/profiles.php?XID=${u.torn_id}`}
                    target="_blank" rel="noreferrer"
                    style={{ color: '#47A6FF', textDecoration: 'none' }}
                  >
                    {u.torn_name}
                  </a>
                </td>
                <td style={{ padding: '8px 12px' }}>
                  <span style={{
                    color: u.role === 'admin' ? '#FFB30F' : u.role === 'moderator' ? '#73DF5D' : '#888',
                  }}>{u.role}</span>
                </td>
                <td style={{ padding: '8px 12px', color: u.subscription_tier === 'premium' ? '#73DF5D' : '#888' }}>
                  {u.subscription_tier}
                </td>
                <td style={{ padding: '8px 12px', color: '#888' }}>{fmtDate(u.created_at)}</td>
                <td style={{ padding: '8px 12px', color: '#888' }}>{fmtDate(u.last_seen)}</td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={6} style={{ padding: '16px 12px', color: '#555' }}>No users yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
