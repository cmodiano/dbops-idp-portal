import type { User } from '../types/common';
import { buildHeaders, parseErrorResponse } from './api_client';

const API_BASE = '/api/v1';

// NOTE: auth_service intentionally uses raw fetch() instead of full api_client functions.
// REASON: refreshAccessToken IS the refresh handler called by api_client's 401 retry logic
//         — using api_client functions would create a circular dependency.
// PARTIAL ALIGNMENT: Uses buildHeaders() and parseErrorResponse() helpers for consistency,
//                    but does NOT use handleAuthenticatedFetch (would be circular).

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!res.ok) {
      const { message } = await parseErrorResponse(res);
      console.warn(`Token refresh failed: ${message}`);
      return null;
    }
    const body = await res.json();
    return body.data?.access_token ?? null;
  } catch (err) {
    console.warn('Token refresh error:', err);
    return null;
  }
}

export async function fetchCurrentUser(token: string): Promise<User | null> {
  try {
    const headers = buildHeaders(token);
    const res = await fetch(`${API_BASE}/auth/me`, { headers });
    if (!res.ok) {
      const { message } = await parseErrorResponse(res);
      console.warn(`fetchCurrentUser failed: ${message}`);
      return null;
    }
    const body = await res.json();
    return body.data ?? null;
  } catch (err) {
    console.warn('fetchCurrentUser error:', err);
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
