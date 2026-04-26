export interface AuthInfo {
  token: string;
  torn_id: number;
  torn_name: string;
  role: string;
  subscription_tier: string;
}

const KEYS = {
  token:    'tbsp_admin_token',
  torn_id:  'tbsp_admin_torn_id',
  name:     'tbsp_admin_name',
  role:     'tbsp_admin_role',
};

export function saveAuth(info: AuthInfo): void {
  localStorage.setItem(KEYS.token,   info.token);
  localStorage.setItem(KEYS.torn_id, String(info.torn_id));
  localStorage.setItem(KEYS.name,    info.torn_name);
  localStorage.setItem(KEYS.role,    info.role);
}

export function clearAuth(): void {
  Object.values(KEYS).forEach(k => localStorage.removeItem(k));
}

export function getStoredRole(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(KEYS.role);
}

export function getStoredName(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(KEYS.name);
}

export function getStoredTornId(): number | null {
  if (typeof window === 'undefined') return null;
  const v = localStorage.getItem(KEYS.torn_id);
  return v ? parseInt(v, 10) : null;
}

export function isLoggedIn(): boolean {
  if (typeof window === 'undefined') return false;
  return !!localStorage.getItem(KEYS.token);
}

export function hasAccess(): boolean {
  const role = getStoredRole();
  return role === 'admin' || role === 'moderator';
}
