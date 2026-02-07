import { describe, it, expect, vi, beforeEach } from 'vitest';
import { refreshAccessToken, fetchCurrentUser, logoutApi } from './auth_service';

describe('auth_service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('refreshAccessToken returns token on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { access_token: 'new-token' } }),
    });

    const result = await refreshAccessToken();
    expect(result).toBe('new-token');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/refresh',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    );
  });

  it('refreshAccessToken returns null on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { message: 'Invalid refresh token' } }),
    });
    const result = await refreshAccessToken();
    expect(result).toBeNull();
  });

  it('fetchCurrentUser returns user data', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { id: 1, username: 'marc' } }),
    });

    const result = await fetchCurrentUser('token123');
    expect(result).toEqual({ id: 1, username: 'marc' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/me',
      expect.objectContaining({ headers: { Authorization: 'Bearer token123' } }),
    );
  });

  it('fetchCurrentUser returns null on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { message: 'Access denied' } }),
    });
    const result = await fetchCurrentUser('bad');
    expect(result).toBeNull();
  });

  it('logoutApi calls POST /auth/logout', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
    await logoutApi();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/logout',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    );
  });
});
