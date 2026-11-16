import { ApiError, login as apiLogin } from './api';

/** The Judge token lives only in sessionStorage (Requirement 13.5). */
export const TOKEN_KEY = 'necromarc.judge_token';

function storage(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

function emit(name: 'auth:changed' | 'auth:expired'): void {
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent(name));
  }
}

export function getToken(): string | null {
  try {
    return storage()?.getItem(TOKEN_KEY) ?? null;
  } catch {
    return null;
  }
}

export function isJudge(): boolean {
  return getToken() !== null;
}

/** Remove the token without dispatching any event. */
export function clearToken(): void {
  try {
    storage()?.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

/** Called by api.ts on a 401 from a protected call. */
export function expireSession(): void {
  clearToken();
  emit('auth:expired');
}

export type LoginResult =
  | { ok: true }
  | { ok: false; kind: 'invalid_credentials' }
  | { ok: false; kind: 'rate_limited'; retryAfter: number | null }
  | { ok: false; kind: 'error'; code: string };

/** Log in; stores the token and dispatches `auth:changed` on success (13.6, 13.7). */
export async function login(username: string, password: string): Promise<LoginResult> {
  try {
    const res = await apiLogin(username, password);
    storage()?.setItem(TOKEN_KEY, res.token);
    emit('auth:changed');
    return { ok: true };
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 401) return { ok: false, kind: 'invalid_credentials' };
      if (e.status === 429) return { ok: false, kind: 'rate_limited', retryAfter: e.retryAfter };
      return { ok: false, kind: 'error', code: e.code };
    }
    return { ok: false, kind: 'error', code: 'NETWORK_ERROR' };
  }
}

/** Clear the token and dispatch `auth:changed` (13.13). */
export function logout(): void {
  clearToken();
  emit('auth:changed');
}
