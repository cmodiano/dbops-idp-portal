import { describe, it, expect, vi, beforeEach } from 'vitest';
import { refreshAccessToken, fetchCurrentUser, logoutApi, portalLogin } from './auth_service';
import * as apiClient from './api_client';

vi.mock('./api_client', async (importOriginal) => {
  const actual = await importOriginal<typeof apiClient>();
  return {
    ...actual,
    parseErrorResponse: vi.fn(),
  };
});

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
      '/api/v1/auth/refresh/',
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
      '/api/v1/auth/me/',
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
      '/api/v1/auth/logout/',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    );
  });

  it('refreshAccessToken returns null when data.access_token missing', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: {} }),
    });
    const result = await refreshAccessToken();
    expect(result).toBeNull();
  });

  it('refreshAccessToken returns null on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    const result = await refreshAccessToken();
    expect(result).toBeNull();
  });

  it('fetchCurrentUser returns null on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    const result = await fetchCurrentUser('token');
    expect(result).toBeNull();
  });

  it('logoutApi does not throw on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
    await expect(logoutApi()).resolves.toBeUndefined();
  });
});

describe('auth_service portalLogin', () => {
  it('returns access_token on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: { access_token: 'token', token_type: 'Bearer', expires_in: 3600 },
      }),
    });

    const result = await portalLogin('user', 'pass');

    expect(result).toEqual({
      access_token: 'token',
      token_type: 'Bearer',
      expires_in: 3600,
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/portal-login/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'user', password: 'pass' }),
      }),
    );
  });

  it('throws with RATE_LIMIT_EXCEEDED code on 429', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { message: 'Too many requests' } }),
    });

    vi.mocked(apiClient.parseErrorResponse).mockResolvedValue({
      message: 'Too many requests',
      body: {},
    } as any);

    await expect(portalLogin('user', 'pass')).rejects.toMatchObject({
      message: 'Too many requests',
      code: 'RATE_LIMIT_EXCEEDED',
      status: 429,
    });
  });

  it('throws with error code from body on 400', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { code: 'INVALID_CREDENTIALS', message: 'Bad credentials' } }),
    });

    vi.mocked(apiClient.parseErrorResponse).mockResolvedValue({
      message: 'Bad credentials',
      body: { error: { code: 'INVALID_CREDENTIALS' } },
    } as any);

    await expect(portalLogin('user', 'wrong')).rejects.toMatchObject({
      message: 'Bad credentials',
      code: 'INVALID_CREDENTIALS',
    });
  });
});
