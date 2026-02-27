import { apiFetch } from './api_client';

export type ApiKeyScope = 'executions' | 'catalog' | 'full'; // pragma: allowlist secret
export type ApiKeyStatus = 'active' | 'expired'; // pragma: allowlist secret

export interface ApiKeyListItem {
  id: number;
  name: string;
  scope: ApiKeyScope | null;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
  status: ApiKeyStatus;
}

export interface ApiKeyCreateRequest {
  name: string;
  scope?: ApiKeyScope | null;
}

export interface ApiKeyCreateResponse {
  id: number;
  name: string;
  scope: ApiKeyScope | null;
  created_at: string;
  raw_key: string;
}

export async function listApiKeys(): Promise<ApiKeyListItem[]> {
  return apiFetch<ApiKeyListItem[]>('/auth/api-keys/');
}

export async function createApiKey(payload: ApiKeyCreateRequest): Promise<ApiKeyCreateResponse> {
  return apiFetch<ApiKeyCreateResponse>('/auth/api-keys/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function revokeApiKey(id: number): Promise<void> {
  return apiFetch<void>(`/auth/api-keys/${id}/`, {
    method: 'DELETE',
  });
}
