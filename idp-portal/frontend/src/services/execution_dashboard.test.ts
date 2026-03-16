/**
 * Tests for execution_dashboard (Story 9.4, 9.10).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as executionDashboard from './execution_dashboard';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
}));

describe('execution_dashboard', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('fetchExecutionStats', () => {
    it('fetches stats with default scope', async () => {
      const mock = { total: 10, completed: 8, failed: 2 };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionDashboard.fetchExecutionStats();

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        expect.stringContaining('scope=mine')
      );
      expect(result).toEqual(mock);
    });

    it('includes filter params when provided', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await executionDashboard.fetchExecutionStats('all', {
        start_date: '2024-01-01',
        status: 'COMPLETED',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('scope=all');
      expect(url).toContain('start_date=2024-01-01');
      expect(url).toContain('status=COMPLETED');
    });
  });

  describe('fetchExecutionTimeSeries', () => {
    it('fetches timeseries data', async () => {
      const mock = [{ date: '2024-01-01', count: 5 }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionDashboard.fetchExecutionTimeSeries();

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        expect.stringContaining('/executions/timeseries')
      );
      expect(result).toEqual(mock);
    });

    it('passes filters to timeseries', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await executionDashboard.fetchExecutionTimeSeries('all', {
        action_id: 1,
        environment: 'PROD',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('action_id=1');
      expect(url).toContain('environment=PROD');
    });
  });

  describe('fetchExecutionTags', () => {
    it('fetches tags list', async () => {
      const mock = ['rac', 'dataguard', 'oracle'];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await executionDashboard.fetchExecutionTags();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/executions/tags');
      expect(result).toEqual(mock);
    });
  });
});
