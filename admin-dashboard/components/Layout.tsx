import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { clearAuth, getStoredName, getStoredRole, hasAccess, isLoggedIn } from '@/lib/auth';

const NAV = [
  { href: '/overview',  label: '📊 Overview'  },
  { href: '/users',     label: '👥 Users'     },
  { href: '/ml',        label: '🤖 ML'        },
  { href: '/payments',  label: '💰 Payments'  },
  { href: '/audit',     label: '📋 Audit Log' },
];

const S = {
  shell: {
    display: 'flex', minHeight: '100vh',
    background: '#0d0d1a', color: '#eee', fontFamily: 'monospace, sans-serif',
  } as React.CSSProperties,
  sidebar: {
    width: 200, background: '#1a1a2e', borderRight: '1px solid #2a2a4a',
    display: 'flex', flexDirection: 'column' as const, padding: '24px 0',
    flexShrink: 0,
  },
  logo: {
    padding: '0 20px 24px', fontSize: 18, fontWeight: 'bold', color: '#47A6FF',
    borderBottom: '1px solid #2a2a4a', marginBottom: 16,
  },
  navItem: (active: boolean): React.CSSProperties => ({
    padding: '10px 20px', cursor: 'pointer', fontSize: 13,
    background: active ? '#2a2a4a' : 'transparent',
    color: active ? '#eee' : '#888',
    borderLeft: active ? '3px solid #47A6FF' : '3px solid transparent',
    userSelect: 'none',
  }),
  main: {
    flex: 1, display: 'flex', flexDirection: 'column' as const,
  },
  topbar: {
    height: 50, background: '#1a1a2e', borderBottom: '1px solid #2a2a4a',
    display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
    padding: '0 24px', gap: 16, fontSize: 13,
  },
  content: { padding: 28, flex: 1 },
  logoutBtn: {
    padding: '4px 12px', background: '#6c3a3a', color: '#eee',
    border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const [name, setName]   = useState('');
  const [role, setRole]   = useState('');

  useEffect(() => {
    if (!isLoggedIn() || !hasAccess()) {
      router.push('/');
      return;
    }
    setName(getStoredName() || '');
    setRole(getStoredRole() || '');
  }, [router]);

  function logout() {
    clearAuth();
    router.push('/');
  }

  return (
    <div style={S.shell}>
      <aside style={S.sidebar}>
        <div style={S.logo}>⚔ TBSP Admin</div>
        {NAV.map(({ href, label }) => (
          <div
            key={href}
            style={S.navItem(router.pathname === href)}
            onClick={() => router.push(href)}
          >
            {label}
          </div>
        ))}
      </aside>

      <main style={S.main}>
        <div style={S.topbar}>
          <span style={{ color: '#888' }}>
            {name} &bull; <span style={{ color: role === 'admin' ? '#FFB30F' : '#73DF5D' }}>{role}</span>
          </span>
          <button style={S.logoutBtn} onClick={logout}>Log out</button>
        </div>
        <div style={S.content}>{children}</div>
      </main>
    </div>
  );
}
