import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { apiFetch } from '@/lib/api';
import { saveAuth, hasAccess, isLoggedIn } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState('');
  const [error,  setError]  = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isLoggedIn() && hasAccess()) router.push('/overview');
  }, [router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Login failed');
        return;
      }
      if (data.role !== 'admin' && data.role !== 'moderator') {
        setError('Access denied — admin or moderator role required');
        return;
      }
      saveAuth(data);
      router.push('/overview');
    } catch {
      setError('Connection error — is the backend running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#0d0d1a', fontFamily: 'monospace, sans-serif',
    }}>
      <div style={{
        width: 360, background: '#1a1a2e', border: '1px solid #2a2a4a',
        borderRadius: 8, padding: 32,
      }}>
        <div style={{ fontSize: 22, fontWeight: 'bold', color: '#47A6FF', marginBottom: 8 }}>
          ⚔ TBSP Admin
        </div>
        <div style={{ color: '#888', fontSize: 13, marginBottom: 24 }}>
          Enter your Torn API key to access the dashboard.
          Only admins and moderators have access.
        </div>

        <form onSubmit={handleLogin}>
          <input
            type="text"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="Torn API key"
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '8px 10px', background: '#0d0d1a',
              border: '1px solid #444', borderRadius: 4,
              color: '#eee', fontSize: 13, marginBottom: 12,
            }}
          />
          {error && (
            <div style={{ color: '#FF5555', fontSize: 12, marginBottom: 10 }}>{error}</div>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '9px', background: loading ? '#1e4070' : '#2a6496',
              color: '#eee', border: 'none', borderRadius: 4,
              cursor: loading ? 'not-allowed' : 'pointer', fontSize: 13, fontWeight: 'bold',
            }}
          >
            {loading ? 'Connecting…' : 'Connect'}
          </button>
        </form>
      </div>
    </div>
  );
}
