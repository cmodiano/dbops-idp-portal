const API_BASE = '/api/v1';

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

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = _getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> ?? {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response = await fetch(`${API_BASE}${path}`, { ...init, headers });

  // 401 interceptor: attempt token refresh and retry once
  if (response.status === 401 && token) {
    const newToken = await _onRefreshNeeded();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE}${path}`, { ...init, headers });
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: { message: 'Unknown error' } }));
    throw new Error(body.error?.message ?? 'Unknown error');
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json();
  return body.data as T;
}

/** GET and return response as Blob (e.g. file download). Uses auth. */
export async function apiFetchBlob(path: string): Promise<Blob> {
  const token = _getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let response = await fetch(`${API_BASE}${path}`, { method: 'GET', headers });
  if (response.status === 401 && token) {
    const newToken = await _onRefreshNeeded();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE}${path}`, { method: 'GET', headers });
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: { message: 'Unknown error' } }));
    throw new Error(body.error?.message ?? 'Unknown error');
  }
  return response.blob();
}

/** POST FormData (no Content-Type header). Returns unwrapped data from JSON body. Uses auth. */
export async function apiPostFormData<T>(path: string, formData: FormData): Promise<{ data: T }> {
  const token = _getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: formData });
  if (response.status === 401 && token) {
    const newToken = await _onRefreshNeeded();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: formData });
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: { message: 'Unknown error' } }));
    throw new Error(body.error?.message ?? 'Unknown error');
  }
  const body = await response.json();
  return body as { data: T };
}
