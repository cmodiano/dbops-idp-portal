import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getHelpContent } from './help_service';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
}));

describe('help_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  describe('getHelpContent', () => {
    it('fetches help content from API and caches it', async () => {
      const mockData = {
        topic_id: 'action-form-integration',
        short: 'Texte court',
        markdown: '# Titre\n\nCorps.',
      };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockData);

      const result = await getHelpContent('action-form-integration');

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        '/api/v1/help/action-form-integration/'
      );
      expect(result).toEqual(mockData);

      // Verify cache was set
      const cached = sessionStorage.getItem('help_action-form-integration');
      expect(cached).not.toBeNull();
      const parsed = JSON.parse(cached!);
      expect(parsed.data).toEqual(mockData);
    });

    it('returns cached data when cache is valid', async () => {
      const mockData = {
        topic_id: 'action-form-integration',
        short: 'Cached',
        markdown: '# Cached',
      };
      sessionStorage.setItem(
        'help_action-form-integration',
        JSON.stringify({ data: mockData, timestamp: Date.now() })
      );

      const result = await getHelpContent('action-form-integration');

      expect(apiClient.apiFetch).not.toHaveBeenCalled();
      expect(result).toEqual(mockData);
    });

    it('fetches from API when cache is expired', async () => {
      const oldData = {
        topic_id: 'action-form-integration',
        short: 'Old',
        markdown: '# Old',
      };
      sessionStorage.setItem(
        'help_action-form-integration',
        JSON.stringify({
          data: oldData,
          timestamp: Date.now() - 11 * 60 * 1000,
        })
      );

      const newData = {
        topic_id: 'action-form-integration',
        short: 'New',
        markdown: '# New',
      };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(newData);

      const result = await getHelpContent('action-form-integration');

      expect(apiClient.apiFetch).toHaveBeenCalled();
      expect(result).toEqual(newData);
    });

    it('returns empty content on 404 error', async () => {
      vi.mocked(apiClient.apiFetch).mockRejectedValue(new Error('Not found'));

      const result = await getHelpContent('unknown-topic');

      expect(result).toEqual({
        topic_id: 'unknown-topic',
        short: '',
        markdown: '',
      });
    });

    it('returns empty content on network error', async () => {
      vi.mocked(apiClient.apiFetch).mockRejectedValue(
        new Error('Network error')
      );

      const result = await getHelpContent('action-form-integration');

      expect(result).toEqual({
        topic_id: 'action-form-integration',
        short: '',
        markdown: '',
      });
    });
  });
});
