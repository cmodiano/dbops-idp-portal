const API_BASE = '/api/v1';

/** Error thrown by apiFetch when response is not ok. Carries HTTP status for 403/400 handling. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    /** Optional parsed JSON body (e.g. { error: { code, message, details } }) for 400 validation details. */
    public responseBody?: { error?: { code?: string; message?: string; details?: Record<string, unknown> } },
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** Token accessor set by AuthProvider. Avoids circular dependency. */
let _getAccessToken: (() => string | null) = () => null;
let _onRefreshNeeded: (() => Promise<string | null>) = async () => null;

export function setAuthAccessors(
  getToken: () => string | null,
  refreshFn: () => Promise<string | null>,
) {
  _getAccessToken = getToken;
  _onRefreshNeeded = refreshFn;
}

// --- Internal helpers (centralised auth / retry / error logic) ---

/** Ensure path has a trailing slash before any query string (avoids Django APPEND_SLASH 301s). */
function ensureTrailingSlash(path: string): string {
  const [base, query] = path.split('?', 2);
  const slashed = base.endsWith('/') ? base : `${base}/`;
  return query !== undefined ? `${slashed}?${query}` : slashed;
}

/** Build HTTP headers with optional auth token and content type. */
export function buildHeaders(
  token: string | null,
  contentType?: string,
  customHeaders?: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = {};
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  if (customHeaders) {
    Object.assign(headers, customHeaders);
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/** Fetch with automatic 401 retry after token refresh. */
export async function handleAuthenticatedFetch(
  path: string,
  init: RequestInit,
  headers: Record<string, string>,
): Promise<Response> {
  const url = `${API_BASE}${ensureTrailingSlash(path)}`;
  let response = await fetch(url, { ...init, headers });

  if (response.status === 401 && _getAccessToken()) {
    const newToken = await _onRefreshNeeded();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      response = await fetch(url, { ...init, headers });
    }
  }

  return response;
}

/** Parse a non-ok Response into an error message and optional body. */
export async function parseErrorResponse(
  response: Response,
  captureBody = false,
): Promise<{ message: string; body?: ApiError['responseBody'] }> {
  const contentType = response.headers.get('content-type');
  const isJson = contentType?.includes('application/json');

  if (isJson) {
    try {
      const body = await response.json();
      const message = body.error?.message ?? `Erreur HTTP ${response.status}`;
      return { message, body: captureBody ? body : undefined };
    } catch {
      return { message: `Erreur HTTP ${response.status}: ${response.statusText}` };
    }
  }

  try {
    const text = await response.text();
    return { message: text || `Erreur HTTP ${response.status}: ${response.statusText}` };
  } catch {
    return { message: `Erreur HTTP ${response.status}: ${response.statusText}` };
  }
}

// --- Public API functions ---

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = _getAccessToken();
  const headers = buildHeaders(token, 'application/json', init?.headers as Record<string, string>);
  const response = await handleAuthenticatedFetch(path, init ?? {}, headers);

  if (!response.ok) {
    const { message, body } = await parseErrorResponse(response, true);
    throw new ApiError(message, response.status, body);
  }

  if (response.status === 204) return undefined as T;
  const body = await response.json();
  return body.data as T;
}

/**
 * Fetch API returning the full JSON body (not just .data).
 * Use when response includes extra fields alongside data (e.g., can_execute, allowed_environments).
 * Includes auth headers and 401 retry logic.
 */
export async function apiFetchRaw<T>(path: string, init?: RequestInit): Promise<T> {
  const token = _getAccessToken();
  const headers = buildHeaders(token, 'application/json', init?.headers as Record<string, string>);
  const response = await handleAuthenticatedFetch(path, init ?? {}, headers);

  if (!response.ok) {
    const { message } = await parseErrorResponse(response);
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

/** GET and return response as Blob (e.g. file download). Uses auth. */
export async function apiFetchBlob(path: string): Promise<Blob> {
  const token = _getAccessToken();
  const headers = buildHeaders(token);
  const response = await handleAuthenticatedFetch(path, { method: 'GET' }, headers);

  if (!response.ok) {
    const { message } = await parseErrorResponse(response);
    throw new ApiError(message, response.status);
  }

  return response.blob();
}

/** POST FormData (no Content-Type header). Returns unwrapped data from JSON body. Uses auth. */
export async function apiPostFormData<T>(path: string, formData: FormData): Promise<{ data: T }> {
  const token = _getAccessToken();
  const headers = buildHeaders(token);
  const response = await handleAuthenticatedFetch(path, { method: 'POST', body: formData }, headers);

  if (!response.ok) {
    const { message } = await parseErrorResponse(response);
    throw new ApiError(message, response.status);
  }

  const body = await response.json();
  return body as { data: T };
}
