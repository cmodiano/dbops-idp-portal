import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiFetch, setAuthAccessors } from './api_client';

describe('apiFetch', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  it('makes a GET request to API_BASE + path', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { items: [] } }),
    });

    const result = await apiFetch('/catalog');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/catalog',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    );
    expect(result).toEqual({ items: [] });
  });

  it('includes Authorization header when token is available', async () => {
    setAuthAccessors(() => 'my-token', async () => null);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: {} }),
    });

    await apiFetch('/test');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/test',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer my-token' }),
      }),
    );
  });

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: { message: 'Server error' } }),
    });

    await expect(apiFetch('/fail')).rejects.toThrow('Server error');
  });

  it('retries with refreshed token on 401', async () => {
    setAuthAccessors(() => 'expired-token', async () => 'refreshed-token');

    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ data: 'ok' }) });

    const result = await apiFetch('/protected');
    expect(global.fetch).toHaveBeenCalledTimes(2);
    // Second call should use refreshed token
    const secondCall = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(secondCall[1].headers.Authorization).toBe('Bearer refreshed-token');
    expect(result).toBe('ok');
  });

  it('does not retry 401 if no token was set', async () => {
    setAuthAccessors(() => null, async () => 'refreshed');

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { message: 'Unauthorized' } }),
    });

    await expect(apiFetch('/no-token')).rejects.toThrow('Unauthorized');
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
