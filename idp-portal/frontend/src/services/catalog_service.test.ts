/**
 * Tests for catalog_service (Story 3.1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as catalogService from './catalog_service';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

describe('catalog_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('fetchCatalogActions', () => {
    it('fetches all catalog actions without filters', async () => {
      const mockActions = [{ id: 1, name: 'Test Action', execution_count: 5 }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockActions);

      const result = await catalogService.fetchCatalogActions();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/catalog/actions');
      expect(result).toEqual(mockActions);
    });

    it('fetches catalog actions with category filter (AC6)', async () => {
      const mockActions = [{ id: 1, name: 'Provisioning Action' }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockActions);

      const result = await catalogService.fetchCatalogActions({ category: 'provisioning' });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/catalog/actions?category=provisioning');
      expect(result).toEqual(mockActions);
    });

    it('fetches catalog actions with tags filter', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await catalogService.fetchCatalogActions({ tags: ['rac', 'dataguard'] });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/catalog/actions?tags=rac%2Cdataguard');
    });

    it('fetches catalog actions with q, engine, environment, impact (Story 3.3, AC9)', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await catalogService.fetchCatalogActions({
        q: 'oracle',
        engine: 'Oracle',
        environment: 'PROD',
        impact: 'high',
      });

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        '/catalog/actions?q=oracle&engine=Oracle&environment=PROD&impact=high'
      );
    });
  });

  describe('fetchCatalogTags (Story 3.3, AC10)', () => {
    it('fetches tags with action counts', async () => {
      const mockTags = [
        { name: 'rac', action_count: 5 },
        { name: 'dataguard', action_count: 2 },
      ];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockTags);

      const result = await catalogService.fetchCatalogTags();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/catalog/tags');
      expect(result).toEqual(mockTags);
    });
  });

  describe('fetchFavorites', () => {
    it('fetches user favorites (AC12)', async () => {
      const mockFavorites = [
        { action_id: 1, created_at: '2026-01-29T12:00:00' },
        { action_id: 2, created_at: '2026-01-29T11:00:00' },
      ];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockFavorites);

      const result = await catalogService.fetchFavorites();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/users/me/favorites');
      expect(result).toEqual(mockFavorites);
    });
  });

  describe('addFavorite', () => {
    it('adds action to favorites (AC13)', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue(undefined);

      await catalogService.addFavorite(101);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/users/me/favorites/101', { method: 'POST' });
    });
  });

  describe('removeFavorite', () => {
    it('removes action from favorites (AC13)', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue(undefined);

      await catalogService.removeFavorite(101);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/users/me/favorites/101', { method: 'DELETE' });
    });
  });

  describe('fetchRecentActions', () => {
    it('fetches recent actions with default limit (AC5)', async () => {
      const mockRecent = [
        { action_id: 1, name: 'Recent Action', last_executed_at: '2026-01-29T12:00:00' },
      ];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockRecent);

      const result = await catalogService.fetchRecentActions();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/users/me/recent-actions?limit=10');
      expect(result).toEqual(mockRecent);
    });

    it('fetches recent actions with custom limit', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await catalogService.fetchRecentActions(5);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/users/me/recent-actions?limit=5');
    });
  });

  describe('fetchCatalogActionById (Story 3.2)', () => {
    it('fetches action detail by ID using apiFetchRaw with auth (AC1, AC6)', async () => {
      const mockResponse = {
        data: {
          id: 1,
          name: 'Test Action',
          description: 'Full description',
          tags: ['oracle'],
        },
        can_execute: true,
        allowed_environments: ['DEV', 'QUAL'],
      };

      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      const result = await catalogService.fetchCatalogActionById(1);

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/catalog/actions/1');
      expect(result.data.id).toBe(1);
      expect(result.can_execute).toBe(true);
      expect(result.allowed_environments).toEqual(['DEV', 'QUAL']);
    });

    it('throws error when action not found (AC6)', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockRejectedValue(new Error('Action non trouvée'));

      await expect(catalogService.fetchCatalogActionById(999)).rejects.toThrow('Action non trouvée');
    });

    it('returns can_execute false for unauthenticated users (AC3)', async () => {
      const mockResponse = {
        data: { id: 1, name: 'Test Action' },
        can_execute: false,
        allowed_environments: [],
      };

      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      const result = await catalogService.fetchCatalogActionById(1);

      expect(result.can_execute).toBe(false);
      expect(result.allowed_environments).toEqual([]);
    });

    it('defaults can_execute to false when not provided', async () => {
      const mockResponse = {
        data: { id: 1, name: 'Test Action' },
        // can_execute and allowed_environments not provided
      };

      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      const result = await catalogService.fetchCatalogActionById(1);

      expect(result.can_execute).toBe(false);
      expect(result.allowed_environments).toEqual([]);
    });
  });
});
