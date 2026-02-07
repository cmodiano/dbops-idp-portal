/**
 * Story 17.12: Feature Flag Service tests.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as featureFlagService from './featureFlagService';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

describe('featureFlagService', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('fetchFeatureFlagsStatus', () => {
    it('calls GET /feature-flags/status/', async () => {
      const mockStatus = { new_ui: true, dark_mode: false };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockStatus);

      const result = await featureFlagService.fetchFeatureFlagsStatus();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/feature-flags/status');
      expect(result).toEqual(mockStatus);
    });
  });

  describe('fetchFeatureFlags', () => {
    it('calls GET /feature-flags/ (admin)', async () => {
      const mockResponse = {
        data: [{ flag_key: 'test', enabled: true, rollout_percent: 100 }],
        source: 'env',
      };
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      const result = await featureFlagService.fetchFeatureFlags();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/feature-flags');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('updateFeatureFlag', () => {
    it('calls PATCH /feature-flags/{flagKey}/ with enabled', async () => {
      const mockResult = { flag_key: 'test', enabled: true, rollout_percent: 100 };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResult);

      const result = await featureFlagService.updateFeatureFlag('test', { enabled: true });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/feature-flags/test', {
        method: 'PATCH',
        body: JSON.stringify({ enabled: true }),
      });
      expect(result).toEqual(mockResult);
    });

    it('calls PATCH with rollout_percent', async () => {
      const mockResult = { flag_key: 'gradual', enabled: true, rollout_percent: 50 };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResult);

      await featureFlagService.updateFeatureFlag('gradual', { rollout_percent: 50 });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/feature-flags/gradual', {
        method: 'PATCH',
        body: JSON.stringify({ rollout_percent: 50 }),
      });
    });
  });
});
