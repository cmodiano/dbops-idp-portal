/**
 * Tests for api_keys_service (Story 71.11, AC #1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listApiKeys, createApiKey, revokeApiKey } from './api_keys_service';
import * as apiClient from './api_client';

describe('api_keys_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('listApiKeys', () => {
    it('fetches the list of API keys via GET /auth/api-keys/', async () => {
      const mockKeys = [
        { id: 1, name: 'ci-key', scope: 'full', created_at: '2024-01-01T00:00:00Z', expires_at: null, is_active: true, status: 'active' },
      ];
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockKeys as any);

      const result = await listApiKeys();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/auth/api-keys/');
      expect(result).toEqual(mockKeys);
    });

    it('propagates error when API rejects', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockRejectedValue(new Error('Network Error'));

      await expect(listApiKeys()).rejects.toThrow('Network Error');
    });
  });

  describe('createApiKey', () => {
    it('sends POST with body and returns ApiKeyCreateResponse', async () => {
      const payload = { name: 'prod-key', scope: 'executions' as const };
      const mockResponse = { id: 2, name: 'prod-key', scope: 'executions', created_at: '2024-01-01T00:00:00Z', raw_key: 'secret123' };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await createApiKey(payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/auth/api-keys/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('revokeApiKey', () => {
    it('sends DELETE /auth/api-keys/{id}/', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(undefined as any);

      await revokeApiKey(42);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/auth/api-keys/42/', { method: 'DELETE' });
    });
  });
});
