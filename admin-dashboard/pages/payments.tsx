import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { apiGet, apiPut } from '@/lib/api';
import { getStoredRole } from '@/lib/auth';

interface Payment {
  id: string;
  torn_id: number;
  xanax_trade_id: string | null;
  days_granted: number;
  created_at: string;
}

interface User {
  torn_id: number;
  torn_name: string;
}

function fmtDate(s: string): string {
  return new Date(s).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [names,    setNames]    = useState<Record<number, string>>({});
  const [error,    setError]    = useState('');
  const [msg,      setMsg]      = useState('');
  // Manual grant state
  const [grantId,   setGrantId]   = useState('');
  const [grantDays, setGrantDays] = useState('30');
  const isAdmin = getStoredRole() === 'admin';

  useEffect(() => {
    apiGet<Payment[]>('/api/admin/payments').then(setPayments).catch(e => setError(e.message));
    // Load user names for display
    apiGet<User[]>('/api/admin/users')
      .then(users => {
        const map: Record<number, string> = {};
        users.forEach(u => { map[u.torn_id] = u.torn_name; });
        setNames(map);
      })
      .catch(() => {});
  }, []);

  async function grantManual(e: React.FormEvent) {
    e.preventDefault();
    const torn_id = parseInt(grantId, 10);
    const days    = parseInt(grantDays, 10);
    if (!torn_id || !days) return;
    const end = new Date(Date.now() + days * 86400_000).toISOString().split('T')[0];
    try {
      await apiPut(`/api/admin/users/${torn_id}/subscription`, { tier: 'premium', end_date: end });
      setMsg(`Granted ${days} days to ${torn_id}`);
      setGrantId('');
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  }

  const totalDays = payments.reduce((s, p) => s + p.days_granted, 0);

  return (
    <Layout>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#eee' }}>Payments ({payments.length})</h2>
        <span style={{ color: '#888', fontSize: 13 }}>{totalDays} days granted total</span>
      </div>

      {error && <div style={{ color: '#FF5555', marginBottom: 10, fontSize: 12 }}>{error}</div>}
      {msg   && <div style={{ color: '#73DF5D', marginBottom: 10, fontSize: 12 }}>{msg}</div>}

      {isAdmin && (
        <div style={{
          background: '#1a1a2e', border: '1px solid #2a2a4a', borderRadius: 8,
          padding: '16px 20px', marginBottom: 24,
        }}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 10 }}>MANUAL GRANT</div>
          <form onSubmit={grantManual} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              placeholder="Torn ID"
              value={grantId}
              onChange={e => setGrantId(e.target.value)}
              style={{
                padding: '5px 8px', background: '#0d0d1a', border: '1px solid #333',
                borderRadius: 4, color: '#eee', fontSize: 12, width: 100,
              }}
            />
            <input
              placeholder="Days"
              value={grantDays}
              onChange={e => setGrantDays(e.target.value)}
              style={{
                padding: '5px 8px', background: '#0d0d1a', border: '1px solid #333',
                borderRadius: 4, color: '#eee', fontSize: 12, width: 60,
              }}
            />
            <button type="submit" style={{
              padding: '5px 14px', background: '#2a6496', color: '#eee',
              border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
            }}>
              Grant premium
            </button>
          </form>
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: '#888', borderBottom: '1px solid #2a2a4a' }}>
              {['Torn ID', 'Name', 'Days', 'Trade ID', 'Date'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '6px 12px', fontWeight: 'normal' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {payments.map(p => (
              <tr key={p.id} style={{ borderBottom: '1px solid #1a1a30' }}>
                <td style={{ padding: '8px 12px', color: '#666' }}>{p.torn_id}</td>
                <td style={{ padding: '8px 12px' }}>
                  <a
                    href={`https://www.torn.com/profiles.php?XID=${p.torn_id}`}
                    target="_blank" rel="noreferrer"
                    style={{ color: '#47A6FF', textDecoration: 'none' }}
                  >
                    {names[p.torn_id] || p.torn_id}
                  </a>
                </td>
                <td style={{ padding: '8px 12px', color: '#73DF5D' }}>{p.days_granted}</td>
                <td style={{ padding: '8px 12px', color: '#555', fontFamily: 'monospace' }}>
                  {p.xanax_trade_id ?? '(manual)'}
                </td>
                <td style={{ padding: '8px 12px', color: '#888' }}>{fmtDate(p.created_at)}</td>
              </tr>
            ))}
            {payments.length === 0 && (
              <tr><td colSpan={5} style={{ padding: '16px 12px', color: '#555' }}>No payments yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
