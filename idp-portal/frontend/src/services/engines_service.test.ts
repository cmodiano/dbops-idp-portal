/**
 * Tests for engines_service (Story 71.11, AC #1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchEnginesForAdmin, updateEngine } from './engines_service';
import * as apiClient from './api_client';

describe('engines_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('fetchEnginesForAdmin', () => {
    it('fetches all engines by default (activeOnly=false)', async () => {
      const mockEngines = [{ id: 1, code: 'oracle', label: 'Oracle', is_active: 1 }];
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockEngines as any);

      const result = await fetchEnginesForAdmin();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/reference/engines?active_only=false');
      expect(result).toEqual(mockEngines);
    });

    it('fetches only active engines when activeOnly=true', async () => {
      const mockEngines = [{ id: 1, code: 'oracle', label: 'Oracle', is_active: 1 }];
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockEngines as any);

      const result = await fetchEnginesForAdmin(true);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/reference/engines?active_only=true');
      expect(result).toEqual(mockEngines);
    });
  });

  describe('updateEngine', () => {
    it('sends PATCH /admin/engines/{id}/ with body JSON', async () => {
      const payload = { label: 'Oracle DB', is_active: 1 };
      const mockResponse = { id: 5, code: 'oracle', label: 'Oracle DB', is_active: 1 };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await updateEngine(5, payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/engines/5/', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });
});
