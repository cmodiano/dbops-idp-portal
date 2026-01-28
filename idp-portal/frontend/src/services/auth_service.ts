import type { User } from '../types/common';

const API_BASE = '/api/v1';

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!res.ok) return null;
    const body = await res.json();
    return body.data?.access_token ?? null;
  } catch {
    return null;
  }
}

export async function fetchCurrentUser(token: string): Promise<User | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const body = await res.json();
    return body.data ?? null;
  } catch {
    return null;
  }
}

export async function logoutApi(): Promise<void> {
  // Best effort logout - don't throw if network fails
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // Network error - continue with logout anyway (clear local state)
  }
}
