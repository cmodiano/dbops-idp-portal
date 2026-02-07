import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiFetch, apiFetchRaw, apiFetchBlob, apiPostFormData, setAuthAccessors, ApiError } from './api_client';

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

  it('throws ApiError on non-ok response with status', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { message: 'Server error' } }),
      text: async () => '',
    });

    try {
      await apiFetch('/fail');
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(500);
      expect((err as ApiError).message).toBe('Server error');
    }
  });

  it('retries with refreshed token on 401', async () => {
    setAuthAccessors(() => 'expired-token', async () => 'refreshed-token');

    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, headers: { get: () => null }, json: async () => ({}), text: async () => '' })
      .mockResolvedValueOnce({ ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ data: 'ok' }), text: async () => '' });

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
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { message: 'Unauthorized' } }),
      text: async () => '',
    });

    await expect(apiFetch('/no-token')).rejects.toThrow('Unauthorized');
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('returns undefined on 204 No Content', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    });

    const result = await apiFetch('/delete');
    expect(result).toBeUndefined();
  });

  it('captures responseBody on error when available', async () => {
    const errorBody = { error: { message: 'Validation failed', details: { field: 'required' } } };
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      headers: { get: () => 'application/json' },
      json: async () => errorBody,
    });

    try {
      await apiFetch('/validate');
      expect.fail('Should have thrown');
    } catch (err) {
      expect((err as ApiError).responseBody).toEqual(errorBody);
    }
  });
});

describe('apiFetchRaw', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  it('returns full JSON body (not just .data)', async () => {
    const fullBody = { data: { items: [] }, can_execute: true, allowed_environments: ['dev'] };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => fullBody,
    });

    const result = await apiFetchRaw('/action/123');
    expect(result).toEqual(fullBody);
  });

  it('includes auth headers and retry logic', async () => {
    setAuthAccessors(() => 'token', async () => 'new-token');

    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, headers: { get: () => null } })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ data: 'ok' }) });

    await apiFetchRaw('/retry-test');
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('throws ApiError on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      headers: { get: () => 'application/json' },
      json: async () => ({ error: { message: 'Access denied' } }),
    });

    await expect(apiFetchRaw('/forbidden')).rejects.toThrow('Access denied');
  });

  it('returns undefined on 204', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    });

    const result = await apiFetchRaw('/no-content');
    expect(result).toBeUndefined();
  });
});

describe('apiFetchBlob', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  it('returns response as Blob', async () => {
    const mockBlob = new Blob(['file content'], { type: 'application/pdf' });
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => mockBlob,
    });

    const result = await apiFetchBlob('/export/audit.pdf');
    expect(result).toBe(mockBlob);
  });

  it('includes auth token in headers', async () => {
    setAuthAccessors(() => 'download-token', async () => null);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob(),
    });

    await apiFetchBlob('/download');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/download',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer download-token' }),
      }),
    );
  });

  it('does not set Content-Type header', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob(),
    });

    await apiFetchBlob('/file');
    const callHeaders = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
    expect(callHeaders['Content-Type']).toBeUndefined();
  });

  it('throws on error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      headers: { get: () => 'text/plain' },
      text: async () => 'File not found',
    });

    await expect(apiFetchBlob('/missing.pdf')).rejects.toThrow('File not found');
  });

  it('retries on 401 with token refresh', async () => {
    setAuthAccessors(() => 'old', async () => 'new');

    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, headers: { get: () => null } })
      .mockResolvedValueOnce({ ok: true, status: 200, blob: async () => new Blob() });

    await apiFetchBlob('/secure-file');
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});

describe('apiPostFormData', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  it('sends FormData without Content-Type header', async () => {
    const formData = new FormData();
    formData.append('file', new Blob(['content']), 'test.txt');

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { file_id: '123' } }),
    });

    await apiPostFormData('/upload', formData);
    const callHeaders = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
    expect(callHeaders['Content-Type']).toBeUndefined();
  });

  it('returns full response body with data field', async () => {
    const responseBody = { data: { file_id: 'abc' } };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => responseBody,
    });

    const result = await apiPostFormData('/upload', new FormData());
    expect(result).toEqual(responseBody);
  });

  it('includes auth token', async () => {
    setAuthAccessors(() => 'upload-token', async () => null);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: {} }),
    });

    await apiPostFormData('/upload', new FormData());
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/upload',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer upload-token' }),
      }),
    );
  });

  it('throws on upload failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 413,
      statusText: 'Payload Too Large',
      headers: { get: () => 'text/plain' },
      text: async () => 'File too large',
    });

    await expect(apiPostFormData('/upload', new FormData())).rejects.toThrow('File too large');
  });

  it('retries on 401', async () => {
    setAuthAccessors(() => 'exp', async () => 'refreshed');

    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, headers: { get: () => null } })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ data: { id: '1' } }) });

    await apiPostFormData('/upload', new FormData());
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});
