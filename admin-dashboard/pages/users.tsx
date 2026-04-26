import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { apiGet, apiPut, apiDelete } from '@/lib/api';
import { getStoredRole } from '@/lib/auth';

interface User {
  torn_id: number;
  torn_name: string;
  role: string;
  subscription_tier: string;
  subscription_end: string | null;
  api_key_status: string;
  last_seen: string | null;
  created_at: string;
}

function fmtDate(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' });
}

function subColor(end: string | null, tier: string): string {
  if (tier === 'free' || !end) return '#888';
  return new Date(end) > new Date() ? '#73DF5D' : '#FF5555';
}

function keyColor(status: string): string {
  return { active: '#73DF5D', paused: '#FFB30F', inactive: '#888', invalid: '#FF5555' }[status] ?? '#888';
}

function roleColor(role: string): string {
  return { admin: '#FFB30F', moderator: '#73DF5D', user: '#888' }[role] ?? '#888';
}

export default function UsersPage() {
  const [users,   setUsers]   = useState<User[]>([]);
  const [error,   setError]   = useState('');
  const [msg,     setMsg]     = useState('');
  const [myRole,  setMyRole]  = useState('');
  const [search,  setSearch]  = useState('');

  useEffect(() => {
    setMyRole(getStoredRole() || '');
    apiGet<User[]>('/api/admin/users').then(setUsers).catch(e => setError(e.message));
  }, []);

  const isAdmin = myRole === 'admin';

  async function changeRole(torn_id: number, role: string) {
    try {
      await apiPut(`/api/admin/users/${torn_id}/role`, { role });
      setUsers(prev => prev.map(u => u.torn_id === torn_id ? { ...u, role } : u));
      setMsg(`Role updated for ${torn_id}`);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  }

  async function changeSub(torn_id: number, tier: string, days: number) {
    const end = new Date(Date.now() + days * 86400_000).toISOString().split('T')[0];
    try {
      await apiPut(`/api/admin/users/${torn_id}/subscription`, { tier, end_date: end });
      setUsers(prev => prev.map(u =>
        u.torn_id === torn_id ? { ...u, subscription_tier: tier, subscription_end: end } : u
      ));
      setMsg(`Subscription updated for ${torn_id}`);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  }

  async function deleteUser(torn_id: number, name: string) {
    if (!confirm(`Delete user ${name} [${torn_id}]? This cannot be undone.`)) return;
    try {
      await apiDelete(`/api/admin/users/${torn_id}`);
      setUsers(prev => prev.filter(u => u.torn_id !== torn_id));
      setMsg(`User ${torn_id} deleted`);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  }

  const filtered = search
    ? users.filter(u =>
        u.torn_name?.toLowerCase().includes(search.toLowerCase()) ||
        String(u.torn_id).includes(search)
      )
    : users;

  const btnBase: React.CSSProperties = {
    padding: '3px 8px', border: 'none', borderRadius: 3, cursor: 'pointer',
    fontSize: 11, fontWeight: 'bold',
  };

  return (
    <Layout>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <h2 style={{ margin: 0, color: '#eee' }}>Users ({users.length})</h2>
        <input
          placeholder="Search name or ID…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            marginLeft: 'auto', padding: '5px 10px', background: '#1a1a2e',
            border: '1px solid #2a2a4a', borderRadius: 4, color: '#eee', fontSize: 12,
          }}
        />
      </div>

      {error && <div style={{ color: '#FF5555', marginBottom: 10, fontSize: 12 }}>{error}</div>}
      {msg   && <div style={{ color: '#73DF5D', marginBottom: 10, fontSize: 12 }}>{msg}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: '#888', borderBottom: '1px solid #2a2a4a' }}>
              {['ID', 'Name', 'Role', 'Subscription', 'Key', 'Last seen', ...(isAdmin ? ['Actions'] : [])].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '6px 10px', fontWeight: 'normal' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(u => (
              <tr key={u.torn_id} style={{ borderBottom: '1px solid #1a1a30' }}>
                <td style={{ padding: '7px 10px', color: '#666' }}>{u.torn_id}</td>

                <td style={{ padding: '7px 10px' }}>
                  <a
                    href={`https://www.torn.com/profiles.php?XID=${u.torn_id}`}
                    target="_blank" rel="noreferrer"
                    style={{ color: '#47A6FF', textDecoration: 'none' }}
                  >
                    {u.torn_name || '—'}
                  </a>
                </td>

                <td style={{ padding: '7px 10px' }}>
                  {isAdmin ? (
                    <select
                      value={u.role}
                      onChange={e => changeRole(u.torn_id, e.target.value)}
                      style={{
                        background: '#0d0d1a', color: roleColor(u.role),
                        border: '1px solid #333', borderRadius: 3, fontSize: 11, padding: '2px 4px',
                      }}
                    >
                      {['user', 'moderator', 'admin'].map(r => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  ) : (
                    <span style={{ color: roleColor(u.role) }}>{u.role}</span>
                  )}
                </td>

                <td style={{ padding: '7px 10px' }}>
                  <span style={{ color: subColor(u.subscription_end, u.subscription_tier) }}>
                    {u.subscription_tier}
                    {u.subscription_end && ` · ${fmtDate(u.subscription_end)}`}
                  </span>
                  {isAdmin && (
                    <span style={{ marginLeft: 6 }}>
                      <button
                        style={{ ...btnBase, background: '#2a4a2a', color: '#73DF5D' }}
                        onClick={() => changeSub(u.torn_id, 'premium', 30)}
                      >+30d</button>
                      <button
                        style={{ ...btnBase, background: '#4a2a2a', color: '#FF5555', marginLeft: 4 }}
                        onClick={() => changeSub(u.torn_id, 'free', 0)}
                      >revoke</button>
                    </span>
                  )}
                </td>

                <td style={{ padding: '7px 10px' }}>
                  <span style={{ color: keyColor(u.api_key_status) }}>{u.api_key_status}</span>
                </td>

                <td style={{ padding: '7px 10px', color: '#666' }}>{fmtDate(u.last_seen)}</td>

                {isAdmin && (
                  <td style={{ padding: '7px 10px' }}>
                    <button
                      style={{ ...btnBase, background: '#3a1a1a', color: '#FF5555' }}
                      onClick={() => deleteUser(u.torn_id, u.torn_name)}
                    >delete</button>
                  </td>
                )}
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={isAdmin ? 7 : 6} style={{ padding: '16px 10px', color: '#555' }}>No users found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
