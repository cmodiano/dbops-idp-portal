import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiFetch, apiFetchRaw, apiFetchBlob, apiPostFormData, setAuthAccessors, setNotificationCallback, ApiError, handleAuthenticatedFetch, calculateRetryDelay, parseErrorResponse, isDbUnavailable503 } from './api_client';
import logger from './logger';

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
      '/api/v1/catalog/',
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
      '/api/v1/test/',
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
      '/api/v1/download/',
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

  it('throws ApiError after 429 retries exhausted', async () => {
    vi.useFakeTimers();
    const mock429 = { status: 429, ok: false, headers: new Headers({ 'Retry-After': '1' }) };
    global.fetch = vi.fn().mockResolvedValue(mock429);

    const p = apiFetchBlob('/rate-limited-file').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(3000);
    const err = await p;
    expect(err).toBeInstanceOf(ApiError);
    vi.useRealTimers();
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
      '/api/v1/upload/',
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

  it('throws ApiError after 429 retries exhausted', async () => {
    vi.useFakeTimers();
    const mock429 = { status: 429, ok: false, headers: new Headers({ 'Retry-After': '1' }) };
    global.fetch = vi.fn().mockResolvedValue(mock429);

    const p = apiPostFormData('/upload-rate-limited', new FormData()).catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(3000);
    const err = await p;
    expect(err).toBeInstanceOf(ApiError);
    vi.useRealTimers();
  });
});

describe('calculateRetryDelay', () => {
  it('returns Retry-After value in milliseconds when header is present', () => {
    expect(calculateRetryDelay(0, '2')).toBe(2000);
    expect(calculateRetryDelay(1, '5')).toBe(5000);
  });

  it('uses exponential backoff when Retry-After is absent', () => {
    expect(calculateRetryDelay(0, null)).toBe(1000);  // 2^0 * 1000
    expect(calculateRetryDelay(1, null)).toBe(2000);  // 2^1 * 1000
    expect(calculateRetryDelay(2, null)).toBe(4000);  // 2^2 * 1000
  });

  it('uses exponential backoff when Retry-After is not a valid number', () => {
    expect(calculateRetryDelay(0, 'invalid')).toBe(1000);
    expect(calculateRetryDelay(1, '')).toBe(2000);
  });

  it('uses exponential backoff when Retry-After is zero or negative', () => {
    expect(calculateRetryDelay(0, '0')).toBe(1000);
    expect(calculateRetryDelay(0, '-1')).toBe(1000);
  });
});

describe('handleAuthenticatedFetch - 429 retry', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('retries after delay specified in Retry-After header', async () => {
    const mock429 = { status: 429, ok: false, headers: new Headers({ 'Retry-After': '2' }) };
    const mock200 = { status: 200, ok: true, json: async () => ({ data: 'success' }), headers: new Headers() };

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock429)
      .mockResolvedValueOnce(mock200);

    const promise = handleAuthenticatedFetch('/test', {}, {});

    await vi.advanceTimersByTimeAsync(2000);

    const response = await promise;
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
  });

  it('uses exponential backoff when Retry-After is missing', async () => {
    const make429 = () => ({ status: 429, ok: false, headers: new Headers() });
    const mock200 = { status: 200, ok: true, headers: new Headers() };

    global.fetch = vi.fn()
      .mockResolvedValueOnce(make429())  // initial
      .mockResolvedValueOnce(make429())  // retry 1 (1s)
      .mockResolvedValueOnce(mock200);   // retry 2 (2s)

    const promise = handleAuthenticatedFetch('/test', {}, {});

    await vi.advanceTimersByTimeAsync(1000); // 1st retry delay
    await vi.advanceTimersByTimeAsync(2000); // 2nd retry delay

    const response = await promise;
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(response.status).toBe(200);
  });

  it('returns response if retry succeeds before max retries', async () => {
    const mock429 = { status: 429, ok: false, headers: new Headers({ 'Retry-After': '1' }) };
    const mock200 = { status: 200, ok: true, json: async () => ({ data: 'ok' }), headers: new Headers() };

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock429)
      .mockResolvedValueOnce(mock200);

    const promise = handleAuthenticatedFetch('/test', {}, {});
    await vi.advanceTimersByTimeAsync(1000);

    const response = await promise;
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(2); // Initial + 1 retry
  });

  it('throws ApiError after max retries exhausted', async () => {
    const mock429 = { status: 429, ok: false, headers: new Headers({ 'Retry-After': '1' }) };
    const mockLogger = vi.spyOn(logger, 'error');

    global.fetch = vi.fn().mockResolvedValue(mock429);

    const p = handleAuthenticatedFetch('/test', {}, {}).catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(3000);
    const err = await p;
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 429,
      message: 'Trop de requêtes. Veuillez patienter 1 seconde avant de réessayer.',
    });

    expect(global.fetch).toHaveBeenCalledTimes(4); // Initial + 3 retries
    expect(mockLogger).toHaveBeenCalledWith(
      'Rate limit exceeded after all retries',
      expect.objectContaining({
        correlation_id: expect.any(String),
        max_retries: 3,
        endpoint: '/test',
      }),
    );
  });

  it('logs first retry at info level, subsequent at warn level', async () => {
    const mockLoggerInfo = vi.spyOn(logger, 'info');
    const mockLoggerWarn = vi.spyOn(logger, 'warn');
    const mock429 = { status: 429, ok: false, headers: new Headers() };
    const mock200 = { status: 200, ok: true, headers: new Headers() };

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock429)
      .mockResolvedValueOnce(mock200);

    const promise = handleAuthenticatedFetch('/test/path', {}, {});
    await vi.advanceTimersByTimeAsync(1000);

    await promise;

    // First retry logged at info level
    expect(mockLoggerInfo).toHaveBeenCalledTimes(1);
    expect(mockLoggerInfo).toHaveBeenCalledWith(
      'Rate limit exceeded, retrying...',
      expect.objectContaining({
        correlation_id: expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/),
        attempt: 1,
        max_retries: 3,
        delay_ms: 1000,
        endpoint: '/test/path',
      }),
    );
    // No subsequent retries, so warn not called
    expect(mockLoggerWarn).not.toHaveBeenCalled();
  });

  it('logs 1 info + 2 warn with same correlation_id for 3 retries', async () => {
    const mockLoggerInfo = vi.spyOn(logger, 'info');
    const mockLoggerWarn = vi.spyOn(logger, 'warn');
    const mock429 = { status: 429, ok: false, headers: new Headers({ 'Retry-After': '1' }) };

    global.fetch = vi.fn().mockResolvedValue(mock429);

    const promise = handleAuthenticatedFetch('/endpoint', {}, {}).catch(() => {}); // Catch ApiError thrown after retries

    await vi.advanceTimersByTimeAsync(3000);

    await promise;

    // First retry at info
    expect(mockLoggerInfo).toHaveBeenCalledTimes(1);
    const correlationId = (mockLoggerInfo.mock.calls[0]![1] as { correlation_id: string }).correlation_id;
    expect(mockLoggerInfo).toHaveBeenCalledWith('Rate limit exceeded, retrying...', expect.objectContaining({ attempt: 1, correlation_id: correlationId }));

    // Subsequent retries at warn
    expect(mockLoggerWarn).toHaveBeenCalledTimes(2);
    expect(mockLoggerWarn).toHaveBeenNthCalledWith(1, 'Rate limit exceeded, retrying...', expect.objectContaining({ attempt: 2, correlation_id: correlationId }));
    expect(mockLoggerWarn).toHaveBeenNthCalledWith(2, 'Rate limit exceeded, retrying...', expect.objectContaining({ attempt: 3, correlation_id: correlationId }));
  });

  it('does not retry for non-429 errors', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ status: 500, ok: false, statusText: 'Internal Server Error', headers: new Headers() });

    const response = await handleAuthenticatedFetch('/test', {}, {});

    expect(response.status).toBe(500);
    expect(global.fetch).toHaveBeenCalledTimes(1); // No retry
  });
});

describe('parseErrorResponse - 429', () => {
  it('returns user-friendly message with Retry-After value (plural)', async () => {
    const response = {
      status: 429,
      headers: new Headers({ 'Retry-After': '30' }),
    } as unknown as Response;

    const result = await parseErrorResponse(response);
    expect(result.message).toBe('Trop de requêtes. Veuillez patienter 30 secondes avant de réessayer.');
  });

  it('returns user-friendly message with Retry-After value (singular)', async () => {
    const response = {
      status: 429,
      headers: new Headers({ 'Retry-After': '1' }),
    } as unknown as Response;

    const result = await parseErrorResponse(response);
    expect(result.message).toBe('Trop de requêtes. Veuillez patienter 1 seconde avant de réessayer.');
  });

  it('returns user-friendly message without Retry-After', async () => {
    const response = {
      status: 429,
      headers: new Headers(),
    } as unknown as Response;

    const result = await parseErrorResponse(response);
    expect(result.message).toBe('Trop de requêtes. Veuillez patienter quelques instants avant de réessayer.');
  });
});

describe('apiFetch - 429 integration', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('throws ApiError with rate limit message after all retries exhausted', async () => {
    const mock429 = {
      status: 429,
      ok: false,
      headers: new Headers({ 'Retry-After': '1' }),
    };

    global.fetch = vi.fn().mockResolvedValue(mock429);

    const p = apiFetch('/rate-limited').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(3000);
    const err = await p;
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 429,
      message: 'Trop de requêtes. Veuillez patienter 1 seconde avant de réessayer.',
    });
  });
});

// ============================================================================
// Story 32.3 — 503 DB_UNAVAILABLE retry tests (Task 5)
// ============================================================================

const DB_UNAVAILABLE_BODY = {
  error: {
    code: 'DB_UNAVAILABLE',
    message: 'Base de données temporairement indisponible après bascule. Veuillez réessayer dans quelques instants.',
    correlation_id: 'test-corr-503',
  },
};

function mock503(retryAfterSeconds?: number): Response {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  if (retryAfterSeconds !== undefined) {
    headers.set('Retry-After', String(retryAfterSeconds));
  }
  return {
    status: 503,
    ok: false,
    headers,
    clone() { return this; },
    json: async () => DB_UNAVAILABLE_BODY,
    text: async () => JSON.stringify(DB_UNAVAILABLE_BODY),
  } as unknown as Response;
}

function mock200(): Response {
  return {
    status: 200,
    ok: true,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => ({ data: { items: [] } }),
  } as unknown as Response;
}

describe('isDbUnavailable503', () => {
  it('returns true for 503 with DB_UNAVAILABLE code', async () => {
    const response = mock503(30);
    expect(await isDbUnavailable503(response)).toBe(true);
  });

  it('returns false for 503 without DB_UNAVAILABLE code', async () => {
    const response = {
      status: 503,
      clone() { return this; },
      json: async () => ({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Maintenance' } }),
    } as unknown as Response;
    expect(await isDbUnavailable503(response)).toBe(false);
  });

  it('returns false for non-503 response', async () => {
    const response = { status: 200, ok: true } as unknown as Response;
    expect(await isDbUnavailable503(response)).toBe(false);
  });

  it('returns false if body is not valid JSON', async () => {
    const response = {
      status: 503,
      clone() { return { json: async () => { throw new SyntaxError('bad json'); } }; },
    } as unknown as Response;
    expect(await isDbUnavailable503(response)).toBe(false);
  });
});

describe('handleAuthenticatedFetch - 503 DB_UNAVAILABLE retry (Task 5)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
    setNotificationCallback(() => {}); // Reset to no-op to avoid cross-test state
  });

  afterEach(() => {
    vi.useRealTimers();
    setNotificationCallback(() => {}); // Restore no-op
  });

  // Task 5.1: retry après Retry-After: 30, succès au 2ème appel
  it('retries after Retry-After delay on 503 DB_UNAVAILABLE, succeeds on 2nd call', async () => {
    const mock503Response = mock503(30);
    const mock200Response = mock200();

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock503Response)
      .mockResolvedValueOnce(mock200Response);

    const promise = handleAuthenticatedFetch('/catalog/actions', {}, {});
    // Advance past the 30s retry delay
    await vi.advanceTimersByTimeAsync(30_000);
    const response = await promise;

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
  });

  // Task 5.2: 3× 503 (initial + 2 retries) → ApiError with status 503
  it('throws ApiError with status 503 after MAX_503_RETRIES exhausted', async () => {
    const mock503Response = mock503(1);

    global.fetch = vi.fn().mockResolvedValue(mock503Response);

    const p = apiFetch('/catalog/actions').catch((e: unknown) => e);
    // Advance time past 2 retry delays (1s each)
    await vi.advanceTimersByTimeAsync(5_000);
    const err = await p;

    // 1 initial + 2 retries = 3 total fetch calls
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(503);
  });

  // Task 5.3: 503 sans Retry-After → utilise backoff par défaut 5s
  it('uses default 5s delay when Retry-After header is absent', async () => {
    const mock503NoHeader = mock503(); // No Retry-After
    const mock200Response = mock200();

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock503NoHeader)
      .mockResolvedValueOnce(mock200Response);

    const promise = handleAuthenticatedFetch('/actions', {}, {});

    // Should not resolve before 5s
    await vi.advanceTimersByTimeAsync(4_999);
    // At this point, fetch was called once but retry not yet triggered
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // After 5s, retry triggers
    await vi.advanceTimersByTimeAsync(1);
    const response = await promise;
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
  });

  // Task 5.4: body DB_UNAVAILABLE est parsé comme message français
  it('propagates French message from DB_UNAVAILABLE body as ApiError message', async () => {
    const mock503Response = mock503(1);

    global.fetch = vi.fn().mockResolvedValue(mock503Response);

    const p = apiFetch('/executions').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(10_000);
    const err = await p;

    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).message).toContain('indisponible');
    expect((err as ApiError).message).toContain('bascule');
  });

  // Task 5.5: callback warning au 1er retry, callback error si épuisé
  it('calls notification callback with warning on first retry, error on exhaustion', async () => {
    const mockNotify = vi.fn();
    setNotificationCallback(mockNotify);

    const mock503Response = mock503(1);
    global.fetch = vi.fn().mockResolvedValue(mock503Response);

    const p = apiFetch('/actions').catch(() => {});
    await vi.advanceTimersByTimeAsync(10_000);
    await p;

    // Warning called exactly once (1st retry only)
    const warningCalls = mockNotify.mock.calls.filter(([type]) => type === 'warning');
    expect(warningCalls).toHaveLength(1);
    expect(warningCalls[0][1]).toMatchObject({ title: 'Service temporairement indisponible' });

    // Error called exactly once (on exhaustion)
    const errorCalls = mockNotify.mock.calls.filter(([type]) => type === 'error');
    expect(errorCalls).toHaveLength(1);
    expect(errorCalls[0][1]).toMatchObject({ title: 'Base de données temporairement indisponible' });
  });

  it('calls notification callback with warning only if 503 retry succeeds', async () => {
    const mockNotify = vi.fn();
    setNotificationCallback(mockNotify);

    const mock503Response = mock503(1);
    const mock200Response = mock200();

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock503Response)
      .mockResolvedValueOnce(mock200Response);

    const promise = handleAuthenticatedFetch('/actions', {}, {});
    await vi.advanceTimersByTimeAsync(2_000);
    const response = await promise;

    expect(response.status).toBe(200);
    const warningCalls = mockNotify.mock.calls.filter(([type]) => type === 'warning');
    const errorCalls = mockNotify.mock.calls.filter(([type]) => type === 'error');
    expect(warningCalls).toHaveLength(1);
    expect(errorCalls).toHaveLength(0);
  });

  it('logs api_503_retry event with correct attributes', async () => {
    const warnSpy = vi.spyOn(logger, 'warn');

    const mock503Response = mock503(30);
    const mock200Response = mock200();

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock503Response)
      .mockResolvedValueOnce(mock200Response);

    const promise = handleAuthenticatedFetch('/catalog/actions', {}, {});
    await vi.advanceTimersByTimeAsync(30_000);
    await promise;

    expect(warnSpy).toHaveBeenCalledWith('api_503_retry', expect.objectContaining({
      attempt: 1,
      max_retries: 2,
      retry_after_seconds: 30,
      endpoint: '/catalog/actions',
      correlation_id: expect.any(String),
    }));
  });

  it('does not retry 503 that is NOT DB_UNAVAILABLE', async () => {
    const non503DbResponse = {
      status: 503,
      ok: false,
      headers: new Headers({ 'Content-Type': 'application/json' }),
      clone() { return this; },
      json: async () => ({ error: { code: 'MAINTENANCE', message: 'Scheduled maintenance' } }),
      text: async () => 'Scheduled maintenance',
    } as unknown as Response;

    global.fetch = vi.fn().mockResolvedValue(non503DbResponse);

    const p = apiFetch('/actions').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(100);
    const err = await p;

    // Only 1 fetch call — no retry for non-DB_UNAVAILABLE 503
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(503);
  });
});

// ============================================================================
// Story 34.2 — setNotificationCallback tests (AC5)
// ============================================================================

describe('setNotificationCallback (Story 34.2 — AC5)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    setAuthAccessors(() => null, async () => null);
    // Reset to no-op default between tests
    setNotificationCallback(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    // Restore no-op default
    setNotificationCallback(() => {});
  });

  it('callback is invoked with ("warning", { title, description, duration }) on 503 DB_UNAVAILABLE first retry', async () => {
    const mockNotify = vi.fn();
    setNotificationCallback(mockNotify);

    const mock503Response = mock503(30);
    const mock200Response = mock200();

    global.fetch = vi.fn()
      .mockResolvedValueOnce(mock503Response)
      .mockResolvedValueOnce(mock200Response);

    const promise = handleAuthenticatedFetch('/catalog/actions', {}, {});
    await vi.advanceTimersByTimeAsync(30_000);
    await promise;

    expect(mockNotify).toHaveBeenCalledTimes(1);
    expect(mockNotify).toHaveBeenCalledWith('warning', {
      title: 'Service temporairement indisponible',
      description: 'Nouvelle tentative en cours...',
      duration: expect.any(Number),
    });
  });

  it('no-op default does not throw when 503 DB_UNAVAILABLE occurs without setNotificationCallback', async () => {
    // Reset to built-in no-op (default state when module is loaded)
    setNotificationCallback(() => {});

    const mock503Response = mock503(1);
    global.fetch = vi.fn().mockResolvedValue(mock503Response);

    // Should not throw — no-op callback is transparent
    const p = apiFetch('/actions').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(10_000);
    const result = await p;

    // ApiError is expected (503 exhausted), but no runtime crash from notification
    expect(result).toBeInstanceOf(ApiError);
  });
});
