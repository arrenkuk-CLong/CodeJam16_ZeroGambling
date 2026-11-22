// Talks to the Django API. Requests go to /api/* on this site and next.config.ts forwards them to Django
// (http://127.0.0.1:8000 by default), so there is no CORS setup and no hardcoded backend URL.
// A signed-in account's bearer token rides along on every call, like Lovable's attachSupabaseAuth.

const SESSION_KEY = 'zg.session';

export interface AuthUser { id: string; email: string; created_at?: string }
export interface StoredSession { token: string; user: AuthUser }

export function readSession(): StoredSession | null {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null') as StoredSession | null; } catch { return null; }
}
export function writeSession(session: StoredSession | null) {
  try { if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session)); else localStorage.removeItem(SESSION_KEY); } catch { /* private mode */ }
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); }
}

export async function call<T>(path: string, body?: unknown, method: 'GET' | 'POST' = 'POST'): Promise<T> {
  const headers: Record<string, string> = {};
  const session = typeof window === 'undefined' ? null : readSession();
  if (session) headers.Authorization = `Bearer ${session.token}`;
  if (method === 'POST') headers['Content-Type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(`/api/${path}`, { method, headers, body: method === 'POST' ? JSON.stringify(body ?? {}) : undefined });
  } catch {
    throw new ApiError('Can’t reach the server. Is the Django backend running?', 0);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : null;
    const code = data && typeof data === 'object' && 'code' in data && data.code ? String(data.code) : undefined;
    throw new ApiError(detail ?? 'Something went wrong on the server. Please try again.', res.status, code);
  }
  return data as T;
}

/** A Lovable server function: called as fn({ data }), resolved by the Django endpoint at `path`. */
export function serverFn<I, O>(path: string) {
  return (opts: { data: I }) => call<O>(path, opts.data);
}
