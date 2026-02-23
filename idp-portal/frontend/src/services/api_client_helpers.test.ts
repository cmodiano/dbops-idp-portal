import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  buildHeaders,
  handleAuthenticatedFetch,
  parseErrorResponse,
  setAuthAccessors,
} from './api_client';

// --- buildHeaders ---

describe('buildHeaders', () => {
  it('returns empty object when no arguments provided', () => {
    const h = buildHeaders(null);
    expect(h).toEqual({});
  });

  it('adds Content-Type when provided', () => {
    const h = buildHeaders(null, 'application/json');
    expect(h).toEqual({ 'Content-Type': 'application/json' });
  });

  it('omits Content-Type when undefined', () => {
    const h = buildHeaders(null, undefined);
    expect(h['Content-Type']).toBeUndefined();
  });

  it('adds Authorization Bearer when token present', () => {
    const h = buildHeaders('my-token');
    expect(h['Authorization']).toBe('Bearer my-token');
  });

  it('omits Authorization when token is null', () => {
    const h = buildHeaders(null, 'application/json');
    expect(h['Authorization']).toBeUndefined();
  });

  it('merges custom headers', () => {
    const h = buildHeaders(null, undefined, { 'X-Custom': 'value' });
    expect(h['X-Custom']).toBe('value');
  });

  it('custom headers override Content-Type if both provided', () => {
    const h = buildHeaders(null, 'application/json', { 'Content-Type': 'text/plain' });
    expect(h['Content-Type']).toBe('text/plain');
  });

  it('Authorization is set after custom headers (token wins)', () => {
    const h = buildHeaders('real-token', undefined, { 'Authorization': 'Bearer fake' });
    expect(h['Authorization']).toBe('Bearer real-token');
  });

  it('combines Content-Type, custom headers, and token', () => {
    const h = buildHeaders('tok', 'application/json', { 'X-Request-Id': '123' });
    expect(h).toEqual({
      'Content-Type': 'application/json',
      'X-Request-Id': '123',
      'Authorization': 'Bearer tok',
    });
  });

  it('handles empty custom headers object', () => {
    const h = buildHeaders('tok', 'application/json', {});
    expect(h).toEqual({
      'Content-Type': 'application/json',
      'Authorization': 'Bearer tok',
    });
  });

  it('handles empty string token (treated as falsy)', () => {
    const h = buildHeaders('', 'application/json');
    expect(h['Authorization']).toBeUndefined();
  });

  it('handles multiple custom headers with override', () => {
    const h = buildHeaders(null, 'text/plain', {
      'X-Header-1': 'value1',
      'X-Header-2': 'value2',
      'Content-Type': 'application/json',
    });
    expect(h['X-Header-1']).toBe('value1');
    expect(h['X-Header-2']).toBe('value2');
    expect(h['Content-Type']).toBe('application/json'); // Custom overrides
  });

  it('token always wins over custom Authorization header', () => {
    const h = buildHeaders('real-token', undefined, {
      'Authorization': 'Bearer fake-token',
      'X-Custom': 'val',
    });
    expect(h['Authorization']).toBe('Bearer real-token');
    expect(h['X-Custom']).toBe('val');
  });

  it('handles only token without Content-Type or custom headers', () => {
    const h = buildHeaders('just-token');
    expect(h).toEqual({ 'Authorization': 'Bearer just-token' });
  });

  it('preserves case of custom header keys', () => {
    const h = buildHeaders(null, undefined, { 'X-Custom-Header': 'value' });
    expect(h['X-Custom-Header']).toBe('value');
  });
});

// --- handleAuthenticatedFetch ---

describe('handleAuthenticatedFetch', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  it('makes fetch to API_BASE + path', async () => {
    const mockResponse = { ok: true, status: 200 } as Response;
    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    const res = await handleAuthenticatedFetch('/test', {}, { 'Content-Type': 'application/json' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/test/',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
    expect(res).toBe(mockResponse);
  });

  it('returns response directly on success (no retry)', async () => {
    setAuthAccessors(() => 'tok', async () => 'new-tok');
    const mockResponse = { ok: true, status: 200 } as Response;
    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    await handleAuthenticatedFetch('/ok', {}, {});
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('retries on 401 when token exists and refresh succeeds', async () => {
    setAuthAccessors(() => 'expired', async () => 'refreshed');

    const headers: Record<string, string> = { 'Authorization': 'Bearer expired' };
    const failRes = { ok: false, status: 401 } as Response;
    const okRes = { ok: true, status: 200 } as Response;
    global.fetch = vi.fn()
      .mockResolvedValueOnce(failRes)
      .mockResolvedValueOnce(okRes);

    const res = await handleAuthenticatedFetch('/retry', {}, headers);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(headers['Authorization']).toBe('Bearer refreshed');
    expect(res).toBe(okRes);
  });

  it('returns 401 response when refresh returns null', async () => {
    setAuthAccessors(() => 'expired', async () => null);

    const failRes = { ok: false, status: 401 } as Response;
    global.fetch = vi.fn().mockResolvedValue(failRes);

    const res = await handleAuthenticatedFetch('/no-refresh', {}, {});
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(res).toBe(failRes);
  });

  it('does not retry 401 when no token set', async () => {
    setAuthAccessors(() => null, async () => 'refreshed');

    const failRes = { ok: false, status: 401 } as Response;
    global.fetch = vi.fn().mockResolvedValue(failRes);

    const res = await handleAuthenticatedFetch('/no-token', {}, {});
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(res).toBe(failRes);
  });

  it('does not retry on non-401 errors', async () => {
    setAuthAccessors(() => 'tok', async () => 'new-tok');

    const failRes = { ok: false, status: 403 } as Response;
    global.fetch = vi.fn().mockResolvedValue(failRes);

    const res = await handleAuthenticatedFetch('/forbidden', {}, {});
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(res).toBe(failRes);
  });

  it('passes init options (method, body) to fetch', async () => {
    const mockResponse = { ok: true, status: 200 } as Response;
    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    await handleAuthenticatedFetch('/post', { method: 'POST', body: '{}' }, {});
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/post/',
      expect.objectContaining({ method: 'POST', body: '{}' }),
    );
  });

  it('retry succeeds but returns non-ok status (e.g. 403)', async () => {
    setAuthAccessors(() => 'tok', async () => 'new');

    const headers: Record<string, string> = {};
    const failRes401 = { ok: false, status: 401 } as Response;
    const failRes403 = { ok: false, status: 403 } as Response;
    global.fetch = vi.fn()
      .mockResolvedValueOnce(failRes401)
      .mockResolvedValueOnce(failRes403);

    const res = await handleAuthenticatedFetch('/forbidden-after-retry', {}, headers);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(res).toBe(failRes403);
  });

  it('handles fetch network error (rejection)', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network failure'));

    await expect(handleAuthenticatedFetch('/network-error', {}, {}))
      .rejects.toThrow('Network failure');
  });

  it('does not mutate original headers object', async () => {
    setAuthAccessors(() => 'initial', async () => 'refreshed');

    const originalHeaders = { 'X-Custom': 'value' };
    const headersCopy = { ...originalHeaders };

    const fail401 = { ok: false, status: 401 } as Response;
    const okRes = { ok: true, status: 200 } as Response;
    global.fetch = vi.fn()
      .mockResolvedValueOnce(fail401)
      .mockResolvedValueOnce(okRes);

    await handleAuthenticatedFetch('/test', {}, headersCopy);

    // Original should not have Authorization added
    expect(originalHeaders).toEqual({ 'X-Custom': 'value' });
    // Copy should have Authorization updated
    expect((headersCopy as Record<string, string>)['Authorization']).toBe('Bearer refreshed');
  });
});

// --- parseErrorResponse ---

describe('parseErrorResponse', () => {
  function makeResponse(
    status: number,
    contentType: string | null,
    jsonBody?: unknown,
    textBody?: string,
    opts?: { jsonThrows?: boolean; textThrows?: boolean },
  ): Response {
    return {
      status,
      statusText: 'Status Text',
      headers: { get: (name: string) => name === 'content-type' ? contentType : null },
      json: opts?.jsonThrows
        ? () => Promise.reject(new Error('parse error'))
        : () => Promise.resolve(jsonBody),
      text: opts?.textThrows
        ? () => Promise.reject(new Error('read error'))
        : () => Promise.resolve(textBody ?? ''),
    } as unknown as Response;
  }

  it('extracts error.message from JSON response', async () => {
    const res = makeResponse(400, 'application/json', { error: { message: 'Bad request' } });
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('Bad request');
  });

  it('falls back to HTTP status when JSON has no error.message', async () => {
    const res = makeResponse(500, 'application/json', { foo: 'bar' });
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('Erreur HTTP 500');
  });

  it('captures body when captureBody is true', async () => {
    const jsonBody = { error: { message: 'err', details: { field: 'oops' } } };
    const res = makeResponse(400, 'application/json', jsonBody);
    const { body } = await parseErrorResponse(res, true);
    expect(body).toEqual(jsonBody);
  });

  it('does not capture body when captureBody is false', async () => {
    const jsonBody = { error: { message: 'err' } };
    const res = makeResponse(400, 'application/json', jsonBody);
    const { body } = await parseErrorResponse(res, false);
    expect(body).toBeUndefined();
  });

  it('uses text body for non-JSON responses', async () => {
    const res = makeResponse(503, 'text/plain', undefined, 'Service Unavailable');
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('Service Unavailable');
  });

  it('falls back to HTTP status when text is empty', async () => {
    const res = makeResponse(404, 'text/plain', undefined, '');
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('Erreur HTTP 404: Status Text');
  });

  it('falls back to HTTP status on JSON parse error', async () => {
    const res = makeResponse(500, 'application/json', undefined, undefined, { jsonThrows: true });
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('Erreur HTTP 500: Status Text');
  });

  it('falls back to HTTP status on text read error', async () => {
    const res = makeResponse(502, 'text/html', undefined, undefined, { textThrows: true });
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('Erreur HTTP 502: Status Text');
  });

  it('handles null content-type as non-JSON', async () => {
    const res = makeResponse(500, null, undefined, 'raw error');
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('raw error');
  });

  it('handles application/json; charset=utf-8 content type', async () => {
    const res = makeResponse(400, 'application/json; charset=utf-8', { error: { message: 'utf8 error' } });
    const { message } = await parseErrorResponse(res);
    expect(message).toBe('utf8 error');
  });

  it('body is undefined by default (captureBody defaults to false)', async () => {
    const res = makeResponse(400, 'application/json', { error: { message: 'e' } });
    const result = await parseErrorResponse(res);
    expect(result.body).toBeUndefined();
  });

  it('body is undefined for non-JSON responses even with captureBody true', async () => {
    const res = makeResponse(500, 'text/plain', undefined, 'error text');
    const result = await parseErrorResponse(res, true);
    expect(result.body).toBeUndefined();
  });
});
