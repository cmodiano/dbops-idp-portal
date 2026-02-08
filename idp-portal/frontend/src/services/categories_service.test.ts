/**
 * Tests for categories_service (Story 2.30).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getCategories, createCategory, updateCategory, deleteCategory } from './categories_service';
import * as apiClient from './api_client';

describe('categories_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('getCategories', () => {
    it('fetches active categories by default', async () => {
      const mockCategories = [
        { id: 1, code: 'patching', label: 'Correctifs', display_order: 20, is_active: 1 },
      ];
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockCategories as any);

      const result = await getCategories();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/reference/categories?active_only=true');
      expect(result).toEqual(mockCategories);
    });

    it('fetches all categories when activeOnly=false', async () => {
      const mockCategories = [
        { id: 1, code: 'patching', label: 'Correctifs', display_order: 20, is_active: 1 },
        { id: 2, code: 'deprecated', label: 'Obsolète', display_order: 99, is_active: 0 },
      ];
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockCategories as any);

      const result = await getCategories(false);

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/reference/categories?active_only=false');
      expect(result).toEqual(mockCategories);
    });

    it('propagates API errors', async () => {
      vi.spyOn(apiClient, 'apiFetchRaw').mockRejectedValue(new Error('Network Error'));

      await expect(getCategories()).rejects.toThrow('Network Error');
    });
  });

  describe('createCategory', () => {
    it('sends POST request with category data', async () => {
      const newCat = { code: 'backup', label: 'Sauvegarde', display_order: 50, is_active: 1 };
      const mockResponse = { id: 3, ...newCat };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await createCategory(newCat);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/categories/', {
        method: 'POST',
        body: JSON.stringify(newCat),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('updateCategory', () => {
    it('sends PATCH request with partial data', async () => {
      const updates = { label: 'Sauvegarde & Restauration', display_order: 55 };
      const mockResponse = { id: 3, code: 'backup', ...updates, is_active: 1 };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await updateCategory(3, updates);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/categories/3/', {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('deleteCategory', () => {
    it('sends DELETE request to soft-delete endpoint', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(undefined as any);

      await deleteCategory(3);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/categories/3/delete/', {
        method: 'DELETE',
      });
    });
  });
});
